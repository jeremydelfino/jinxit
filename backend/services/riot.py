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
    Retry sur 5xx avec backoff — MATCH-V5 peut mettre du temps à indexer la partie.
    """
    routing  = ROUTING.get(region.upper(), "europe")
    platform = PLATFORM_PREFIX.get(region.upper(), "EUW1")
    match_id = f"{platform}_{riot_game_id}"
    url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{match_id}"

    MAX_RETRIES  = 5
    RETRY_DELAYS = [5, 15, 30, 60, 120]

    for attempt in range(MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                res = await client.get(url, headers=get_headers())

            if res.status_code == 200:
                return res.json()

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

    return None