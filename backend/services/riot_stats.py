"""
services/riot_stats.py
Pull et cache des stats MATCH-V5 par joueur (winrate global, winrate champion, forme).
Cache en mémoire avec TTL 30 min pour éviter de flood l'API Riot.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from services.riot import ROUTING, get_headers
from services.riot_limiter import riot_limiter
import httpx

logger = logging.getLogger(__name__)

# ─── Cache en mémoire ────────────────────────────────────────
_STATS_CACHE: dict = {}
CACHE_TTL_MINUTES = 30
N_GAMES = 20

# Queues à essayer dans l'ordre : ranked solo → ranked flex → toutes les queues classées
QUEUE_FALLBACKS = [420, 440, None]   # None = pas de filtre queue


def _cache_get(puuid: str) -> dict | None:
    entry = _STATS_CACHE.get(puuid)
    if not entry:
        return None
    if datetime.utcnow() > entry["expires_at"]:
        del _STATS_CACHE[puuid]
        return None
    return entry["data"]


def _cache_set(puuid: str, data: dict):
    _STATS_CACHE[puuid] = {
        "data":       data,
        "expires_at": datetime.utcnow() + timedelta(minutes=CACHE_TTL_MINUTES),
    }


async def _fetch_match_ids(puuid: str, region: str, count: int = N_GAMES) -> tuple[list[str], str | None]:
    """
    Retourne (match_ids, error_reason).
    Essaie ranked solo, puis flex, puis toutes queues si rien trouvé.
    """
    routing = ROUTING.get(region.upper(), "europe")
    last_status = None
    short = puuid[:16]

    for queue in QUEUE_FALLBACKS:
        q_str    = f"&queue={queue}" if queue else ""
        q_label  = f"queue={queue}"  if queue else "all_queues"
        url = (
            f"https://{routing}.api.riotgames.com"
            f"/lol/match/v5/matches/by-puuid/{puuid}/ids"
            f"?count={count}{q_str}"
        )
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                async with riot_limiter:
                    r = await c.get(url, headers=get_headers())
            last_status = r.status_code

            if r.status_code == 200:
                ids = r.json()
                if ids:
                    if queue != 420:
                        logger.info(f"📜 {short} → {len(ids)} matchs trouvés via fallback {q_label}")
                    return ids, None
                # 200 mais liste vide → on continue avec la queue suivante
                logger.debug(f"📜 {short} → 0 matchs sur {q_label}, fallback...")
                continue

            if r.status_code in (401, 403):
                logger.error(f"🔑 Riot API key invalide/expirée ({r.status_code}) sur {short}")
                return [], f"riot_key_{r.status_code}"
            if r.status_code == 404:
                logger.warning(f"❓ Puuid {short} introuvable côté Riot (404)")
                return [], "puuid_not_found"
            if r.status_code == 429:
                logger.warning(f"⏱️  Rate-limit Riot (429) sur {short}")
                return [], "rate_limit"
            logger.warning(f"⚠️  Riot {r.status_code} sur {short} ({q_label})")

        except httpx.TimeoutException:
            logger.warning(f"⏱️  Timeout fetch_match_ids {short} ({q_label})")
            return [], "timeout"
        except Exception as e:
            logger.error(f"❌ _fetch_match_ids {short} ({q_label}): {e}")
            return [], f"exception:{type(e).__name__}"

    return [], f"no_matches_any_queue (last_http={last_status})"


async def _fetch_match(match_id: str, routing: str) -> dict | None:
    url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            async with riot_limiter:
                r = await c.get(url, headers=get_headers())
                if r.status_code == 200:
                    return r.json()
                if r.status_code in (401, 403, 429):
                    logger.warning(f"⚠️  _fetch_match {match_id}: HTTP {r.status_code}")
                return None
    except Exception as e:
        logger.error(f"_fetch_match error {match_id}: {e}")
        return None


async def get_player_stats(puuid: str, region: str, current_champ: str | None = None) -> dict:
    """
    Retourne un dict avec :
      winrate_global, winrate_champ, forme_5, n_games, n_games_champ
      + error (str|None) : raison si stats par défaut
    """
    cached = _cache_get(puuid)
    if cached is not None:
        return _compute_stats(cached, current_champ)

    routing = ROUTING.get(region.upper(), "europe")
    match_ids, err = await _fetch_match_ids(puuid, region, N_GAMES)

    if not match_ids:
        return _default_stats(error=err or "no_match_ids")

    tasks   = [_fetch_match(mid, routing) for mid in match_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    games_raw = []
    fail_count = 0
    for match in results:
        if not match or isinstance(match, Exception):
            fail_count += 1
            continue
        part = next(
            (p for p in match["info"]["participants"] if p["puuid"] == puuid),
            None,
        )
        if part:
            games_raw.append({
                "win":         part["win"],
                "champion":    part["championName"],
                "kills":       part["kills"],
                "deaths":      part["deaths"],
                "assists":     part["assists"],
                "game_end_ts": match["info"].get("gameEndTimestamp", 0),
            })

    if not games_raw:
        return _default_stats(error=f"all_match_fetches_failed ({fail_count}/{len(match_ids)})")

    # Tri par récence (plus récent d'abord) — Riot renvoie déjà dans l'ordre mais on s'en assure
    games_raw.sort(key=lambda g: g["game_end_ts"], reverse=True)

    _cache_set(puuid, games_raw)
    logger.info(f"📊 {puuid[:16]} → {len(games_raw)} games chargées")
    return _compute_stats(games_raw, current_champ)


def _compute_stats(games: list[dict], current_champ: str | None) -> dict:
    if not games:
        return _default_stats(error="empty_games_list")

    wins_global = sum(1 for g in games if g["win"])
    wr_global   = wins_global / len(games)

    champ_games = [g for g in games if g["champion"] == current_champ] if current_champ else []
    wr_champ    = (sum(1 for g in champ_games if g["win"]) / len(champ_games)) if champ_games else 0.50

    recent_5 = games[:5]
    forme_5  = sum(1 for g in recent_5 if g["win"]) / len(recent_5) if recent_5 else 0.50

    return {
        "winrate_global": round(wr_global, 3),
        "winrate_champ":  round(wr_champ,  3),
        "forme_5":        round(forme_5,   3),
        "n_games":        len(games),
        "n_games_champ":  len(champ_games),
        "error":          None,
    }


def _default_stats(error: str | None = None) -> dict:
    return {
        "winrate_global": 0.50,
        "winrate_champ":  0.50,
        "forme_5":        0.50,
        "n_games":        0,
        "n_games_champ":  0,
        "error":          error,
    }