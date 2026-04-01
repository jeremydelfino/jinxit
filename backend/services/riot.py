import httpx
import os
from dotenv import load_dotenv
import asyncio
import logging
logger = logging.getLogger(__name__)

load_dotenv()

REGIONS = {
    "EUW": "euw1",
    "NA":  "na1",
    "KR":  "kr",
    "BR":  "br1",
    "EUN": "eun1",
    "JP":  "jp1",
    "LAN": "la1",
    "LAS": "la2",
    "OCE": "oc1",
    "TR":  "tr1",
    "RU":  "ru",
}

ROUTING = {
    "EUW": "europe",
    "EUN": "europe",
    "TR":  "europe",
    "RU":  "europe",
    "NA":  "americas",
    "BR":  "americas",
    "LAN": "americas",
    "LAS": "americas",
    "KR":  "asia",
    "JP":  "asia",
    "OCE": "sea",
}

PLATFORM_PREFIX = {
    "EUW": "EUW1",
    "EUN": "EUN1",
    "TR":  "TR1",
    "RU":  "RU1",
    "NA":  "NA1",
    "BR":  "BR1",
    "KR":  "KR",
    "JP":  "JP1",
    "LAN": "LA1",
    "LAS": "LA2",
    "OCE": "OC1",
}


def get_headers() -> dict:
    return {"X-Riot-Token": os.getenv("RIOT_API_KEY")}


async def get_account_by_riot_id(game_name: str, tag_line: str, region: str) -> dict:
    routing = ROUTING.get(region.upper(), "europe")
    url = f"https://{routing}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers=get_headers())
        res.raise_for_status()
        return res.json()


async def get_summoner_by_puuid(puuid: str, region: str) -> dict:
    platform = REGIONS.get(region.upper(), "euw1")
    url = f"https://{platform}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers=get_headers())
        res.raise_for_status()
        return res.json()


async def get_rank_by_puuid(puuid: str, region: str) -> list:
    platform = REGIONS.get(region.upper(), "euw1")
    url = f"https://{platform}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"
    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers=get_headers())
        res.raise_for_status()
        return res.json()


async def get_live_game_by_puuid(puuid: str, region: str) -> dict | None:
    """
    Récupère la partie live d'un joueur via Spectator V5.
    Retry automatique sur les erreurs 5xx (502, 503, 504) — sporadiques côté Riot.
    """
    platform = REGIONS.get(region.upper(), "euw1")
    url = f"https://{platform}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{puuid}"

    MAX_RETRIES  = 3
    RETRY_DELAYS = [1, 3, 7]   # secondes entre chaque tentative

    for attempt in range(MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                res = await client.get(url, headers=get_headers())

            # Pas en jeu
            if res.status_code == 404:
                return None

            # Erreurs clé API — inutile de retenter
            if res.status_code in (401, 403):
                logger.error(f"get_live_game_by_puuid {res.status_code} — vérifie la clé API Riot dans .env")
                return None

            # Rate limit — attendre le header Retry-After
            if res.status_code == 429:
                retry_after = int(res.headers.get("Retry-After", 5))
                logger.warning(f"get_live_game_by_puuid 429 — rate limited, attente {retry_after}s")
                await asyncio.sleep(retry_after)
                return None

            # Erreurs serveur Riot (502, 503, 504) — on retente
            if res.status_code in (500, 502, 503, 504):
                delay = RETRY_DELAYS[attempt]
                logger.warning(
                    f"get_live_game_by_puuid {res.status_code} (tentative {attempt + 1}/{MAX_RETRIES}) "
                    f"— retry dans {delay}s"
                )
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(delay)
                    continue
                # Dernière tentative échouée → on abandonne silencieusement
                return None

            res.raise_for_status()
            return res.json()

        except httpx.TimeoutException:
            delay = RETRY_DELAYS[attempt]
            logger.warning(
                f"get_live_game_by_puuid timeout (tentative {attempt + 1}/{MAX_RETRIES}) "
                f"— retry dans {delay}s"
            )
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(delay)
                continue
            return None

        except Exception as e:
            logger.error(f"get_live_game_by_puuid erreur inattendue: {e}")
            return None

    return None


async def get_match_history(puuid: str, region: str, count: int = 10) -> list:
    routing = ROUTING.get(region.upper(), "europe")
    url = (
        f"https://{routing}.api.riotgames.com"
        f"/lol/match/v5/matches/by-puuid/{puuid}/ids"
        f"?count={count}&queue=420"
    )
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(url, headers=get_headers())
            if res.status_code != 200:
                return []
            match_ids = res.json()
    except Exception:
        return []

    async def fetch_one(match_id: str) -> dict | None:
        u = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{match_id}"
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                res = await client.get(u, headers=get_headers())
                return res.json() if res.status_code == 200 else None
        except Exception:
            return None

    try:
        results = await asyncio.wait_for(
            asyncio.gather(*[fetch_one(mid) for mid in match_ids]),
            timeout=20.0,
        )
    except asyncio.TimeoutError:
        results = []

    return [r for r in results if r is not None]


async def get_match_result(puuid: str, riot_game_id: str, region: str) -> dict | None:
    """
    Résout une game terminée via MATCH-V5.
    Retry sur 5xx/404 avec backoff — MATCH-V5 peut mettre du temps à indexer la partie.
    Retourne un dict parsé avec winner_team, first_blood, etc.
    """
    routing  = ROUTING.get(region.upper(), "europe")
    platform = PLATFORM_PREFIX.get(region.upper(), "EUW1")
    match_id = f"{platform}_{riot_game_id}"
    url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{match_id}"

    MAX_RETRIES  = 5
    RETRY_DELAYS = [5, 15, 30, 60, 120]

    raw = None
    for attempt in range(MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                res = await client.get(url, headers=get_headers())

            if res.status_code == 200:
                raw = res.json()
                break

            if res.status_code == 404:
                delay = RETRY_DELAYS[attempt]
                logger.info(
                    f"get_match_result 404 pour {match_id} (tentative {attempt + 1}/{MAX_RETRIES}) "
                    f"— pas encore indexé, retry dans {delay}s"
                )
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(delay)
                    continue
                return None

            if res.status_code == 429:
                retry_after = int(res.headers.get("Retry-After", 10))
                logger.warning(f"get_match_result 429 — attente {retry_after}s")
                await asyncio.sleep(retry_after)
                continue

            if res.status_code in (500, 502, 503, 504):
                delay = RETRY_DELAYS[attempt]
                logger.warning(f"get_match_result {res.status_code} — retry dans {delay}s")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(delay)
                    continue
                return None

            logger.error(f"get_match_result statut inattendu {res.status_code} pour {match_id}")
            return None

        except httpx.TimeoutException:
            delay = RETRY_DELAYS[attempt]
            logger.warning(f"get_match_result timeout (tentative {attempt + 1}) — retry dans {delay}s")
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(delay)
                continue
            return None

        except Exception as e:
            logger.error(f"get_match_result erreur: {e}")
            return None

    if not raw:
        return None

    return _parse_match_result(raw)


def _parse_match_result(raw: dict) -> dict | None:
    """
    Transforme le JSON brut MATCH-V5 en dict exploitable par resolve_bets.
    Retourne winner_team ('blue'|'red'), first_blood, first_tower_side, etc.
    """
    try:
        info         = raw.get("info", {})
        participants = info.get("participants", [])
        teams        = info.get("teams", [])

        if not participants or not teams:
            logger.error("_parse_match_result: participants ou teams manquants")
            return None

        # ── Gagnant ─────────────────────────────────────────
        winner_team_id = None
        for t in teams:
            if t.get("win"):
                winner_team_id = t.get("teamId")
                break

        if winner_team_id is None:
            logger.error(f"_parse_match_result: aucun gagnant trouvé dans teams={teams}")
            return None

        # teamId 100 = blue, 200 = red (convention Riot immuable)
        winner_team = "blue" if winner_team_id == 100 else "red"

        # ── First blood ──────────────────────────────────────
        first_blood = None
        for p in participants:
            if p.get("firstBloodKill"):
                first_blood = "blue" if p.get("teamId") == 100 else "red"
                break

        # ── Objectifs ────────────────────────────────────────
        team_data = {t["teamId"]: t for t in teams if "teamId" in t}

        def obj_side(team_id_won: int | None) -> str | None:
            if team_id_won is None:
                return None
            return "blue" if team_id_won == 100 else "red"

        first_tower_side  = None
        first_dragon_side = None
        first_baron_side  = None

        for tid, t in team_data.items():
            objs = t.get("objectives", {})
            if objs.get("tower",  {}).get("first"):
                first_tower_side  = obj_side(tid)
            if objs.get("dragon", {}).get("first"):
                first_dragon_side = obj_side(tid)
            if objs.get("baron",  {}).get("first"):
                first_baron_side  = obj_side(tid)

        # ── Durée ────────────────────────────────────────────
        duration_sec = info.get("gameDuration", 0)
        duration_min = duration_sec / 60

        # ── Stats joueurs ────────────────────────────────────
        kda_positive   = {}  # puuid -> bool
        player_stats   = {}  # puuid -> {kills, deaths, assists, damage, ...}
        top_damage_val = -1
        top_damage_champ = None

        for p in participants:
            puuid    = p.get("puuid", "")
            kills    = p.get("kills",   0)
            deaths   = p.get("deaths",  0)
            assists  = p.get("assists", 0)
            damage   = p.get("totalDamageDealtToChampions", 0)
            champ    = p.get("championName", "")
            team_id  = p.get("teamId", 0)

            kda = (kills + assists) / max(deaths, 1)
            kda_positive[puuid] = deaths == 0 or kda > 0

            player_stats[puuid] = {
                "kills":   kills,
                "deaths":  deaths,
                "assists": assists,
                "kda":     round(kda, 2),
                "damage":  damage,
                "champ":   champ,
                "side":    "blue" if team_id == 100 else "red",
            }

            if damage > top_damage_val:
                top_damage_val   = damage
                top_damage_champ = champ

        # ── Jungle gap ───────────────────────────────────────
        # Smite = summoner spell id 11
        junglers = [
            p for p in participants
            if p.get("summoner1Id") == 11 or p.get("summoner2Id") == 11
        ]

        jungle_gap_side = None
        if len(junglers) == 2:
            jg0, jg1 = junglers[0], junglers[1]
            def jg_score(p):
                kda    = (p.get("kills", 0) + p.get("assists", 0)) / max(p.get("deaths", 1), 1)
                dmg    = p.get("totalDamageDealtToChampions", 0)
                obj    = p.get("neutralMinionsKilled", 0)
                return kda * 0.4 + (dmg / 5000) * 0.3 + (obj / 50) * 0.3

            s0 = jg_score(jg0)
            s1 = jg_score(jg1)
            diff = abs(s0 - s1)

            if diff > 0.3:  # seuil de gap significatif
                if s0 > s1:
                    jungle_gap_side = "blue" if jg0.get("teamId") == 100 else "red"
                else:
                    jungle_gap_side = "blue" if jg1.get("teamId") == 100 else "red"
            else:
                jungle_gap_side = "none"

        logger.info(
            f"_parse_match_result → winner={winner_team} | fb={first_blood} | "
            f"tower={first_tower_side} | dragon={first_dragon_side} | "
            f"baron={first_baron_side} | duration={duration_min:.1f}min | "
            f"top_dmg={top_damage_champ} | jg_gap={jungle_gap_side}"
        )

        return {
            "winner_team":       winner_team,
            "first_blood":       first_blood,
            "first_tower_side":  first_tower_side,
            "first_dragon_side": first_dragon_side,
            "first_baron_side":  first_baron_side,
            "duration_min":      duration_min,
            "kda_positive":      kda_positive,
            "player_stats":      player_stats,
            "top_damage_champ":  top_damage_champ,
            "jungle_gap_side":   jungle_gap_side,
        }

    except Exception as e:
        logger.error(f"_parse_match_result exception: {e}")
        return None