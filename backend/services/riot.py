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

# Préfixe plateforme pour construire le match ID complet (ex: KR_8149145538)
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
    try:
        platform = REGIONS.get(region.upper(), "euw1")
        url = f"https://{platform}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{puuid}"
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(url, headers=get_headers())
            if res.status_code == 404:
                return None
            if res.status_code in (401, 403):
                logger.error(f"get_live_game_by_puuid {res.status_code} — vérifie la clé API dans .env")
                return None
            if res.status_code == 429:
                retry_after = int(res.headers.get("Retry-After", 5))
                await asyncio.sleep(retry_after)
                return None
            res.raise_for_status()
            return res.json()
    except Exception as e:
        logger.error(f"get_live_game_by_puuid error: {e}")
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
    - Appel direct par match ID (plus besoin du puuid pour chercher)
    - Détection jungler via individualPosition (seul champ fiable post-game,
      les spell IDs sont None dans MATCH-V5)
    """
    try:
        routing = ROUTING.get(region.upper(), "europe")
        prefix  = PLATFORM_PREFIX.get(region.upper(), "EUW1")

        # ── Appel direct par match ID ─────────────────────────
        # riot_game_id en DB est le numéro seul (ex: 8149145538)
        # On construit le match ID complet (ex: KR_8149145538)
        match_id = f"{prefix}_{riot_game_id}"
        url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{match_id}"

        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(url, headers=get_headers())
            if res.status_code != 200:
                logger.warning(f"get_match_result: {match_id} → HTTP {res.status_code}")
                return None
            match_data = res.json()

        info         = match_data["info"]
        participants = info["participants"]
        teams        = info["teams"]
        duration_s   = info.get("gameDuration", 0)

        # ── Équipe gagnante ───────────────────────────────────
        winner_team = None
        for team in teams:
            if team.get("win"):
                winner_team = "blue" if team["teamId"] == 100 else "red"
                break

        # ── First Blood ───────────────────────────────────────
        first_blood_champ = None
        for p in participants:
            if p.get("firstBloodKill"):
                first_blood_champ = p.get("championName")
                break

        # ── Objectifs par équipe ──────────────────────────────
        objectives = {}
        for team in teams:
            side = "blue" if team["teamId"] == 100 else "red"
            obj  = team.get("objectives", {})
            objectives[side] = {
                "first_tower":  obj.get("tower",  {}).get("first", False),
                "first_dragon": obj.get("dragon", {}).get("first", False),
                "first_baron":  obj.get("baron",  {}).get("first", False),
            }

        first_tower_side  = next((s for s, o in objectives.items() if o["first_tower"]),  None)
        first_dragon_side = next((s for s, o in objectives.items() if o["first_dragon"]), None)
        first_baron_side  = next((s for s, o in objectives.items() if o["first_baron"]),  None)

        duration_min = duration_s / 60

        # ── Stats par joueur ──────────────────────────────────
        # individualPosition est fiable post-game : TOP / JUNGLE / MIDDLE / BOTTOM / UTILITY
        # Les spell IDs sont None dans MATCH-V5 — on ne s'en sert pas ici
        player_stats: dict[str, dict] = {}
        for p in participants:
            k = p.get("kills",   0)
            d = p.get("deaths",  0)
            a = p.get("assists", 0)
            kda = (k + a) / max(d, 1)

            position  = (p.get("individualPosition") or p.get("teamPosition") or "").upper()
            is_jungle = position == "JUNGLE"

            player_stats[p["puuid"]] = {
                "championName": p.get("championName", ""),
                "side":         "blue" if p.get("teamId") == 100 else "red",
                "kills":        k,
                "deaths":       d,
                "assists":      a,
                "kda":          round(kda, 2),
                "damage":       p.get("totalDamageDealtToChampions", 0),
                "is_jungle":    is_jungle,
                "objectives":   p.get("neutralMinionsKilled", 0),
                "position":     position,
            }

        # ── KDA positif { puuid: bool } ───────────────────────
        kda_positive = {
            puuid: (s["kills"] + s["assists"]) > s["deaths"]
            for puuid, s in player_stats.items()
        }

        # ── Top dégâts global ─────────────────────────────────
        top_damage_champ = max(
            player_stats.values(),
            key=lambda s: s["damage"],
            default=None,
        )
        top_damage_champ_name = top_damage_champ["championName"] if top_damage_champ else None

        # ── Jungle Gap ────────────────────────────────────────
        junglers = {puuid: s for puuid, s in player_stats.items() if s["is_jungle"]}
        jungle_gap_side = None

        logger.info(f"   🌿 Junglers détectés: {len(junglers)} — {[(s['championName'], s['side']) for s in junglers.values()]}")

        if len(junglers) == 2:
            j_list = list(junglers.values())
            j_blue = next((s for s in j_list if s["side"] == "blue"), None)
            j_red  = next((s for s in j_list if s["side"] == "red"),  None)

            if j_blue and j_red:
                def jg_score(j: dict) -> float:
                    return j["kda"] * 0.35 + (j["damage"] / 1000) * 0.35 + j["objectives"] * 0.30

                score_blue = jg_score(j_blue)
                score_red  = jg_score(j_red)
                total      = score_blue + score_red

                if total > 0:
                    ratio = max(score_blue, score_red) / total
                    logger.info(f"   🌿 JG scores — blue: {score_blue:.2f} ({j_blue['championName']}) | red: {score_red:.2f} ({j_red['championName']}) | ratio: {ratio:.2f}")
                    if ratio > 0.55:
                        jungle_gap_side = "blue" if score_blue > score_red else "red"
                        logger.info(f"   🌿 Jungle Gap détecté → {jungle_gap_side}")
                    else:
                        logger.info(f"   🌿 Pas de Jungle Gap (ratio trop faible)")

        elif len(junglers) != 2:
            logger.warning(f"   ⚠️ Jungle Gap impossible — {len(junglers)} jungler(s) détecté(s) au lieu de 2")

        return {
            "winner_team":          winner_team,
            "first_blood":          first_blood_champ,
            "first_tower_side":     first_tower_side,
            "first_dragon_side":    first_dragon_side,
            "first_baron_side":     first_baron_side,
            "duration_s":           duration_s,
            "duration_min":         round(duration_min, 2),
            "kda_positive":         kda_positive,
            "player_stats":         player_stats,
            "top_damage_champ":     top_damage_champ_name,
            "jungle_gap_side":      jungle_gap_side,
        }

    except Exception as e:
        logger.error(f"get_match_result error: {e}")
        return None