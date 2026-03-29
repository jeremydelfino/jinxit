import httpx
from typing import Optional

ESPORTS_API   = "https://esports-api.lolesports.com/persisted/gw"
API_KEY       = "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"
HEADERS       = {"x-api-key": API_KEY}

LEAGUE_IDS = {
    "LEC":    "98767991302996019",
    "LCK":    "98767991310872058",
    "LCS":    "98767991299243165",
    "LPL":    "98767991314006698",
    "WORLDS": "98767975604431411",
    "MSI":    "98767991325878492",
}



CURRENT_TOURNAMENT_IDS = {
    "98767991302996019": "115548424304940735",  # LEC Split 1 2026
    "98767991310872058": "115548106590082745",  # LCK Split 1 2026
    "98767991299243165": "115564596163517554",  # LCS Split 1 2026
    "98767991314006698": "115610660442964993",  # LPL Split 1 2026
    "105266103462388553": "115826472385208906", # LFL Split 1 2026 
}


ALL_LEAGUE_IDS = list(LEAGUE_IDS.values())

async def get_completed_events(tournament_id: str) -> dict:
    async with httpx.AsyncClient(timeout=12) as client:
        r = await client.get(
            f"{ESPORTS_API}/getCompletedEvents",
            headers=HEADERS,
            params={"hl": "fr-FR", "tournamentId": tournament_id},
        )
        r.raise_for_status()
        return r.json()

async def get_teams(team_slug: str = None) -> dict:
    params = {"hl": "fr-FR"}
    if team_slug:
        params["id"] = team_slug
    async with httpx.AsyncClient(timeout=12) as client:
        r = await client.get(f"{ESPORTS_API}/getTeams", headers=HEADERS, params=params)
        r.raise_for_status()
        return r.json()

async def get_schedule(league_ids: list[str] = None, page_token: str = None) -> dict:
    params = {"hl": "fr-FR"}
    ids    = league_ids or ALL_LEAGUE_IDS
    params["leagueId"] = ",".join(ids)
    if page_token:
        params["pageToken"] = page_token
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{ESPORTS_API}/getSchedule", headers=HEADERS, params=params)
        r.raise_for_status()
        return r.json()


async def get_live() -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{ESPORTS_API}/getLive", headers=HEADERS, params={"hl": "fr-FR"})
        r.raise_for_status()
        return r.json()


async def get_event_details(match_id: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{ESPORTS_API}/getEventDetails",
            headers=HEADERS,
            params={"hl": "fr-FR", "id": match_id},
        )
        r.raise_for_status()
        return r.json()


async def get_standings(tournament_id: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{ESPORTS_API}/getStandings",
            headers=HEADERS,
            params={"hl": "fr-FR", "tournamentId": tournament_id},
        )
        r.raise_for_status()
        return r.json()

async def get_current_tournament_id(league_id: str) -> Optional[str]:
    """
    Retourne le tournamentId actif.
    Priorité : IDs hardcodés 2026 → fallback API dynamique.
    """
    # Priorité aux IDs hardcodés (toujours à jour)
    if league_id in CURRENT_TOURNAMENT_IDS:
        return CURRENT_TOURNAMENT_IDS[league_id]

    # Fallback dynamique pour Worlds/MSI dont l'ID change chaque édition
    try:
        data        = await get_tournaments_for_league(league_id)
        leagues     = data.get("data", {}).get("leagues", [])
        tournaments = []
        for league in leagues:
            tournaments.extend(league.get("tournaments", []))

        if not tournaments:
            return None

        now = datetime.now(timezone.utc).date()

        # Chercher un tournoi actif
        for t in sorted(tournaments, key=lambda x: x.get("startDate", ""), reverse=True):
            start = t.get("startDate", "")
            end   = t.get("endDate",   "")
            try:
                s = datetime.strptime(start[:10], "%Y-%m-%d").date()
                e = datetime.strptime(end[:10],   "%Y-%m-%d").date()
                if s <= now <= e:
                    return t["id"]
            except Exception:
                continue

        # Fallback : le plus récent
        past = [t for t in tournaments if t.get("startDate", "9999")[:10] <= now.isoformat()]
        if past:
            return sorted(past, key=lambda t: t.get("startDate", ""), reverse=True)[0]["id"]

        return None
    except Exception:
        return None