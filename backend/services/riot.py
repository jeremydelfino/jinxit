import httpx
import os
from dotenv import load_dotenv

load_dotenv()

RIOT_API_KEY = os.getenv("RIOT_API_KEY")

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

HEADERS = {"X-Riot-Token": RIOT_API_KEY}


async def get_account_by_riot_id(game_name: str, tag_line: str, region: str) -> dict:
    routing = ROUTING.get(region.upper(), "europe")
    url = f"https://{routing}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers=HEADERS)
        res.raise_for_status()
        return res.json()


async def get_summoner_by_puuid(puuid: str, region: str) -> dict:
    platform = REGIONS.get(region.upper(), "euw1")
    url = f"https://{platform}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers=HEADERS)
        res.raise_for_status()
        return res.json()


async def get_rank_by_puuid(puuid: str, region: str) -> list:
    platform = REGIONS.get(region.upper(), "euw1")
    url = f"https://{platform}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"
    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers=HEADERS)
        res.raise_for_status()
        return res.json()


async def get_live_game_by_puuid(puuid: str, region: str) -> dict | None:
    try:
        platform = REGIONS.get(region.upper(), "euw1")
        url = f"https://{platform}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{puuid}"
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=HEADERS)
            if res.status_code == 404:
                return None
            res.raise_for_status()
            return res.json()
    except Exception:
        return None


async def get_match_history(puuid: str, region: str, count: int = 10) -> list:
    routing = ROUTING.get(region.upper(), "europe")
    url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?count={count}&queue=420"
    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers=HEADERS)
        res.raise_for_status()
        match_ids = res.json()

    matches = []
    for match_id in match_ids:
        url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{match_id}"
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=HEADERS)
            if res.status_code == 200:
                matches.append(res.json())
    return matches


async def get_match_result(puuid: str, riot_game_id: str, region: str) -> dict | None:
    """
    Récupère le résultat d'une partie terminée via MATCH-V5.
    Cherche parmi les derniers matchs du joueur celui qui correspond au riot_game_id.

    Retourne :
        {
            "winner_team": "blue" | "red",
            "first_blood": "ChampionName" | None,
        }
    ou None si la partie n'est pas encore disponible.
    """
    try:
        routing = ROUTING.get(region.upper(), "europe")

        # Récupérer les IDs des derniers matchs du joueur
        url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?count=5"
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(url, headers=HEADERS)
            if res.status_code != 200:
                return None
            match_ids = res.json()

        # Chercher la partie correspondante
        # Le riot_game_id du spectator (ex: "8149059668") est le gameId numérique
        # Le match_id MATCH-V5 est au format "EUW1_8149059668"
        target_match_id = None
        for mid in match_ids:
            # Extraire la partie numérique : "EUW1_8149059668" → "8149059668"
            numeric_part = mid.split("_")[-1]
            if numeric_part == str(riot_game_id):
                target_match_id = mid
                break

        if not target_match_id:
            # Pas encore disponible dans MATCH-V5
            return None

        # Récupérer les détails du match
        url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{target_match_id}"
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(url, headers=HEADERS)
            if res.status_code != 200:
                return None
            match_data = res.json()

        participants = match_data["info"]["participants"]
        teams        = match_data["info"]["teams"]

        # Trouver l'équipe gagnante (teamId 100 = blue, 200 = red)
        winner_team = None
        for team in teams:
            if team.get("win"):
                winner_team = "blue" if team["teamId"] == 100 else "red"
                break

        # Trouver le first blood
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