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
    platform = REGIONS.get(region.upper(), "euw1")
    url = f"https://{platform}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{puuid}"
    try:
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

async def get_match_result_by_game_id(riot_game_id: str, game) -> dict | None:
    # Prendre le puuid d'un participant pour trouver la région
    all_participants = game.blue_team + game.red_team
    if not all_participants:
        return None

    # Trouver la région via le premier puuid qui a une région connue
    # On cherche dans searched_players
    puuid = all_participants[0].get("puuid")
    if not puuid:
        return None

    # Essayer les routings asia/europe/americas
    for routing in ["asia", "europe", "americas"]:
        try:
            url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/KR_{riot_game_id}"
            async with httpx.AsyncClient() as client:
                res = await client.get(url, headers=HEADERS, timeout=10)
                if res.status_code == 200:
                    data = res.json()
                    info = data["info"]

                    # Qui a gagné ?
                    blue_win = any(
                        p["win"] for p in info["participants"] if p["teamId"] == 100
                    )
                    winner = "blue" if blue_win else "red"

                    # First blood — premier participant avec firstBloodKill=True
                    first_blood_champ = None
                    for p in info["participants"]:
                        if p.get("firstBloodKill"):
                            first_blood_champ = p["championName"]
                            break

                    return {
                        "winner": winner,
                        "first_blood_champion": first_blood_champ,
                    }
        except Exception:
            continue

    return None