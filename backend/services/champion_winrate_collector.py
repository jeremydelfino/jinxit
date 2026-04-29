"""
services/champion_winrate_collector.py
Collecte les winrates de champions à partir d'un échantillon Master+.

Pipeline :
  1. Pull leaderboards Master+ via LEAGUE-V4 (max ~300 puuids par région)
  2. Pull les 50 dernières games en queue 420 par puuid (capped pour rate limit)
  3. Dédupliquer les match_ids
  4. Pull les détails de chaque match (parallélisé avec semaphore)
  5. Agréger par (champion, lane, region) et par paires (synergies)
  6. Upsert en DB

Cadence recommandée : 1x par semaine (mercredi 6h UTC).
"""
import asyncio
import logging
from collections import defaultdict
from datetime import datetime
import httpx

from database import SessionLocal
from models.champion_stats import ChampionStats
from models.champion_synergy import ChampionSynergy
from services.riot import ROUTING, get_headers
from services.riot_league import get_master_plus_puuids
from services.job_runner import tracked_job

logger = logging.getLogger(__name__)

# ─── Config ───────────────────────────────────────────────────
REGIONS_TO_SAMPLE   = ["EUW", "KR"]
PUUIDS_PER_TIER     = 100   # 100 challenger + 100 gm + 100 master = 300 par région
MATCHES_PER_PUUID   = 30    # Master+ joue beaucoup → 30 récentes suffit
MAX_CONCURRENT_API  = 10    # rate limit Riot : 100 req / 2min en prod, donc ok
MIN_GAMES_PER_CHAMP = 20    # filtre bruit : on n'écrit pas si < 20 games

LANE_MAPPING = {
    "TOP":     "TOP",
    "JUNGLE":  "JUNGLE",
    "MIDDLE":  "MID",
    "BOTTOM":  "ADC",
    "UTILITY": "SUPPORT",
}


async def _fetch_match_ids(puuid: str, region: str, count: int = MATCHES_PER_PUUID) -> list[str]:
    routing = ROUTING.get(region.upper(), "europe")
    url = (
        f"https://{routing}.api.riotgames.com"
        f"/lol/match/v5/matches/by-puuid/{puuid}/ids"
        f"?queue=420&count={count}"
    )
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(url, headers=get_headers())
            return r.json() if r.status_code == 200 else []
    except Exception:
        return []


async def _fetch_match_detail(match_id: str, routing: str, sem: asyncio.Semaphore) -> dict | None:
    async with sem:
        url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{match_id}"
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(url, headers=get_headers())
                if r.status_code == 200:
                    return r.json()
                if r.status_code == 429:
                    retry_after = int(r.headers.get("Retry-After", 5))
                    logger.warning(f"429 sur {match_id}, attente {retry_after}s")
                    await asyncio.sleep(retry_after)
                    # Une seule retry
                    async with httpx.AsyncClient(timeout=10) as c2:
                        r2 = await c2.get(url, headers=get_headers())
                        return r2.json() if r2.status_code == 200 else None
        except Exception:
            return None
    return None


async def _collect_for_region(region: str) -> tuple[dict, dict]:
    """
    Retourne (champion_stats_raw, synergy_stats_raw) pour une région.
    """
    logger.info(f"[champ_collector] région {region} — start")

    puuids = await get_master_plus_puuids(region, max_per_tier=PUUIDS_PER_TIER)
    if not puuids:
        logger.warning(f"[champ_collector] {region}: aucun puuid récupéré, skip")
        return {}, {}

    logger.info(f"[champ_collector] {region}: {len(puuids)} puuids")

    # Pull match ids en parallèle (semaphore léger pour ne pas spam)
    sem_ids = asyncio.Semaphore(MAX_CONCURRENT_API)
    async def get_ids_throttled(p):
        async with sem_ids:
            return await _fetch_match_ids(p, region)

    all_match_id_lists = await asyncio.gather(*[get_ids_throttled(p) for p in puuids])
    unique_match_ids: set[str] = set()
    for ml in all_match_id_lists:
        unique_match_ids.update(ml)

    logger.info(f"[champ_collector] {region}: {len(unique_match_ids)} match_ids uniques")

    # Pull les détails de chaque match
    routing = ROUTING.get(region.upper(), "europe")
    sem_match = asyncio.Semaphore(MAX_CONCURRENT_API)

    matches: list[dict] = []
    BATCH_SIZE = 500
    match_id_list = list(unique_match_ids)

    for i in range(0, len(match_id_list), BATCH_SIZE):
        batch    = match_id_list[i:i + BATCH_SIZE]
        results  = await asyncio.gather(*[_fetch_match_detail(mid, routing, sem_match) for mid in batch])
        matches.extend(m for m in results if m)
        logger.info(f"[champ_collector] {region}: batch {i // BATCH_SIZE + 1} fetched, total={len(matches)}")
        # Petite pause entre batches
        if i + BATCH_SIZE < len(match_id_list):
            await asyncio.sleep(2)

    logger.info(f"[champ_collector] {region}: {len(matches)} matches détaillés récupérés")

    # ── Agrégation ───────────────────────────────────────────
    # champion_stats[(champ, lane)] = {wins, total, kda_sum, kp_sum}
    champion_data: dict[tuple[str, str], dict] = defaultdict(lambda: {
        "wins": 0, "total": 0, "kda_sum": 0.0, "kp_sum": 0.0,
    })

    # synergy_data[(champA, champB)] = {wins, total}  (clé triée)
    synergy_data: dict[tuple[str, str], dict] = defaultdict(lambda: {"wins": 0, "total": 0})

    for match in matches:
        info         = match.get("info", {})
        participants = info.get("participants", [])
        if len(participants) != 10:
            continue

        # Filter parties trop courtes (remakes < 5min)
        if info.get("gameDuration", 0) < 300:
            continue

        # Group par teamId pour kill participation et synergies
        teams = defaultdict(list)
        for p in participants:
            teams[p.get("teamId")].append(p)

        for team_id, team_players in teams.items():
            team_kills = sum(p.get("kills", 0) for p in team_players)
            team_total_dmg = sum(p.get("totalDamageDealtToChampions", 0) for p in team_players)

            for p in team_players:
                champ = p.get("championName", "")
                pos   = p.get("teamPosition", "") or p.get("individualPosition", "")
                lane  = LANE_MAPPING.get(pos, "")
                if not champ or not lane:
                    continue

                kills   = p.get("kills",   0)
                deaths  = p.get("deaths",  0)
                assists = p.get("assists", 0)
                win     = bool(p.get("win", False))
                dmg     = p.get("totalDamageDealtToChampions", 0)

                kda        = (kills + assists) / max(deaths, 1)
                kp         = (kills + assists) / max(team_kills, 1)
                dmg_share  = dmg / max(team_total_dmg, 1)

                key = (champ, lane)
                champion_data[key]["total"]         += 1
                champion_data[key]["wins"]          += int(win)
                champion_data[key]["kda_sum"]       += kda
                champion_data[key]["kp_sum"]        += kp
                champion_data[key]["dmg_share_sum"] += dmg_share

            # Synergies : toutes les paires de champions de cette équipe
            for i in range(len(team_players)):
                for j in range(i + 1, len(team_players)):
                    c1 = team_players[i].get("championName", "")
                    c2 = team_players[j].get("championName", "")
                    if not c1 or not c2:
                        continue
                    pair = tuple(sorted([c1, c2]))
                    synergy_data[pair]["total"] += 1
                    synergy_data[pair]["wins"]  += int(team_players[i].get("win", False))

    return dict(champion_data), dict(synergy_data)


def _persist_champion_stats(
    champion_data: dict[tuple[str, str], dict],
    region: str,
    db,
) -> int:
    """Upsert dans champion_stats. Retourne le nb de lignes écrites."""
    # On a besoin du total games par tier pour calculer le pickrate
    total_games_by_lane: dict[str, int] = defaultdict(int)
    for (champ, lane), data in champion_data.items():
        total_games_by_lane[lane] += data["total"]

    written = 0
    for (champ, lane), data in champion_data.items():
        if data["total"] < MIN_GAMES_PER_CHAMP:
            continue

        winrate       = data["wins"] / data["total"]
        avg_kda       = data["kda_sum"]       / data["total"]
        avg_kp        = data["kp_sum"]        / data["total"]
        avg_dmg_share = data["dmg_share_sum"] / data["total"]
        pickrate      = data["total"] / max(total_games_by_lane[lane] / 5, 1)  # /5 car 1 lane par team

        existing = db.query(ChampionStats).filter(
            ChampionStats.champion == champ,
            ChampionStats.tier     == "MASTER",
            ChampionStats.lane     == lane,
            ChampionStats.region   == region,
        ).first()

        if existing:
            existing.n_games       = data["total"]
            existing.wins          = data["wins"]
            existing.winrate       = round(winrate, 4)
            existing.pickrate      = round(pickrate, 4)
            existing.avg_kda       = round(avg_kda, 3)
            existing.avg_kp        = round(avg_kp, 3)
            existing.avg_dmg_share = round(avg_dmg_share, 3)
        else:
            db.add(ChampionStats(
                champion      = champ,
                tier          = "MASTER",
                lane          = lane,
                region        = region,
                n_games       = data["total"],
                wins          = data["wins"],
                winrate       = round(winrate, 4),
                pickrate      = round(pickrate, 4),
                avg_kda       = round(avg_kda, 3),
                avg_kp        = round(avg_kp, 3),
                avg_dmg_share = round(avg_dmg_share, 3),
            ))
        written += 1

    db.commit()
    return written


def _persist_synergies(
    synergy_data: dict[tuple[str, str], dict],
    champion_data: dict[tuple[str, str], dict],
    region: str,
    db,
) -> int:
    """Upsert dans champion_synergies. Calcule synergy_score = wr_joint - wr_moyen_solo."""
    # WR solo de chaque champion (toutes lanes confondues)
    solo_wr: dict[str, float] = {}
    for (champ, lane), data in champion_data.items():
        if data["total"] >= MIN_GAMES_PER_CHAMP:
            existing_wr  = solo_wr.get(champ, (0, 0))
            new_total    = existing_wr[1] + data["total"]
            new_wins     = existing_wr[0] + data["wins"]
            solo_wr[champ] = (new_wins, new_total)
    solo_wr_norm = {c: w / max(t, 1) for c, (w, t) in solo_wr.items()}

    written = 0
    MIN_PAIR_GAMES = 50  # paire jouée moins de 50 fois → bruit
    for (c1, c2), data in synergy_data.items():
        if data["total"] < MIN_PAIR_GAMES:
            continue
        wr_pair = data["wins"] / data["total"]

        wr_avg = (solo_wr_norm.get(c1, 0.50) + solo_wr_norm.get(c2, 0.50)) / 2
        synergy_score = wr_pair - wr_avg

        existing = db.query(ChampionSynergy).filter(
            ChampionSynergy.champion_a == c1,
            ChampionSynergy.champion_b == c2,
            ChampionSynergy.tier       == "MASTER",
            ChampionSynergy.region     == region,
        ).first()

        if existing:
            existing.n_games       = data["total"]
            existing.wins          = data["wins"]
            existing.winrate       = round(wr_pair, 4)
            existing.synergy_score = round(synergy_score, 4)
        else:
            db.add(ChampionSynergy(
                champion_a    = c1,
                champion_b    = c2,
                tier          = "MASTER",
                region        = region,
                n_games       = data["total"],
                wins          = data["wins"],
                winrate       = round(wr_pair, 4),
                synergy_score = round(synergy_score, 4),
            ))
        written += 1

    db.commit()
    return written


@tracked_job("refresh_champion_winrates")
async def refresh_champion_winrates() -> dict:
    """
    Job principal : sample Master+ EUW + KR, écrit ChampionStats + ChampionSynergy.
    """
    db = SessionLocal()
    total_champ_rows  = 0
    total_synergy_rows = 0

    try:
        # Aggregate combiné EUW+KR pour ALL region aussi
        all_champ_data: dict[tuple[str, str], dict] = defaultdict(lambda: {
            "wins": 0, "total": 0, "kda_sum": 0.0, "kp_sum": 0.0,
        })
        all_synergy_data: dict[tuple[str, str], dict] = defaultdict(lambda: {"wins": 0, "total": 0})

        for region in REGIONS_TO_SAMPLE:
            try:
                champ_data, synergy_data = await _collect_for_region(region)
            except Exception as e:
                logger.error(f"[champ_collector] {region} échec : {e}", exc_info=True)
                continue

            # Persist par région
            total_champ_rows  += _persist_champion_stats(champ_data, region, db)
            total_synergy_rows += _persist_synergies(synergy_data, champ_data, region, db)

            # Agrège pour la région ALL
            for k, v in champ_data.items():
                all_champ_data[k]["wins"]    += v["wins"]
                all_champ_data[k]["total"]   += v["total"]
                all_champ_data[k]["kda_sum"] += v["kda_sum"]
                all_champ_data[k]["kp_sum"]  += v["kp_sum"]
            for k, v in synergy_data.items():
                all_synergy_data[k]["wins"]  += v["wins"]
                all_synergy_data[k]["total"] += v["total"]

        # Persist région ALL (utile pour _draft_score qui ne se soucie pas de la région)
        total_champ_rows   += _persist_champion_stats(dict(all_champ_data), "ALL", db)
        total_synergy_rows += _persist_synergies(dict(all_synergy_data), dict(all_champ_data), "ALL", db)

    finally:
        db.close()

    return {
        "records_processed": total_champ_rows + total_synergy_rows,
        "metadata": {
            "champion_rows": total_champ_rows,
            "synergy_rows":  total_synergy_rows,
            "regions":       REGIONS_TO_SAMPLE,
            "sampled_at":    datetime.utcnow().isoformat(),
        },
    }