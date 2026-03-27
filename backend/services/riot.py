import httpx
import os
from dotenv import load_dotenv

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
    try:
        platform = REGIONS.get(region.upper(), "euw1")
        url = f"https://{platform}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{puuid}"
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(url, headers=get_headers())
            if res.status_code == 404:
                return None
            if res.status_code in (401, 403):
                import logging
                logging.getLogger(__name__).error(
                    f"get_live_game_by_puuid {res.status_code} — vérifie la clé API dans .env"
                )
                return None
            res.raise_for_status()
            if res.status_code == 429:
                retry_after = int(res.headers.get("Retry-After", 5))
                await asyncio.sleep(retry_after)
                return None
            return res.json()
            

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"get_live_game_by_puuid error: {e}")
        return None


async def get_match_history(puuid: str, region: str, count: int = 10) -> list:
    routing = ROUTING.get(region.upper(), "europe")
    url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?count={count}&queue=420"
    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers=get_headers())
        res.raise_for_status()
        match_ids = res.json()

    matches = []
    for match_id in match_ids:
        url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{match_id}"
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=get_headers())
            if res.status_code == 200:
                matches.append(res.json())
    return matches


async def get_match_result(puuid: str, riot_game_id: str, region: str) -> dict | None:
    try:
        routing = ROUTING.get(region.upper(), "europe")

        url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?count=5"
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(url, headers=get_headers())
            if res.status_code != 200:
                return None
            match_ids = res.json()

        target_match_id = None
        for mid in match_ids:
            numeric_part = mid.split("_")[-1]
            if numeric_part == str(riot_game_id):
                target_match_id = mid
                break

        if not target_match_id:
            return None

        url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{target_match_id}"
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(url, headers=get_headers())
            if res.status_code != 200:
                return None
            match_data = res.json()

        participants = match_data["info"]["participants"]
        teams        = match_data["info"]["teams"]

        winner_team = None
        for team in teams:
            if team.get("win"):
                winner_team = "blue" if team["teamId"] == 100 else "red"
                break

        first_blood_champ = None
        for p in participants:
            if p.get("firstBloodKill"):
                first_blood_champ = p.get("championName")
                break

        return {
            "winner_team": winner_team,
            "first_blood": first_blood_champ,
        }

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"get_match_result error: {e}")
        return None