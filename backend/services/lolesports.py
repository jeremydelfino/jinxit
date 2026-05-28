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
    "98767991302996019": "115548668058343983",  # LEC Split 2 2026
    "98767991310872058": "115548106590082745",  # LCK Split 1 2026
    "98767991299243165": "115564596163517554",  # LCS Split 1 2026
    "98767991314006698": "115610660442964993",  # LPL Split 1 2026
    "105266103462388553": "115826472385208906", # LFL Split 1 2026
}



ALL_LEAGUE_IDS = list(LEAGUE_IDS.values())

# ─── Cache mémoire des tournois par ligue ────────────────────
import time
from datetime import datetime, timezone, timedelta

_TOURNAMENTS_CACHE: dict[str, tuple[float, list[dict]]] = {}  # league_id -> (fetched_at, tournaments)
_CACHE_TTL = 86400  # 24h

async def get_recent_tournament_ids(
    league_id: str,
    window_days: int = 90,
) -> list[str]:
    """
    Renvoie les IDs des tournois d'une ligue dont la fenêtre [start, end]
    chevauche les `window_days` derniers jours (donc actifs ou récemment terminés).
    Mis en cache 24h par ligue.
    """
    now_ts = time.time()
    cached = _TOURNAMENTS_CACHE.get(league_id)
    if cached and (now_ts - cached[0]) < _CACHE_TTL:
        tournaments = cached[1]
    else:
        try:
            data = await get_tournaments_for_league(league_id)
            leagues = data.get("data", {}).get("leagues", [])
            tournaments = [t for lg in leagues for t in lg.get("tournaments", [])]
            _TOURNAMENTS_CACHE[league_id] = (now_ts, tournaments)
        except Exception:
            # En cas d'échec API, on réutilise le cache périmé s'il existe
            tournaments = cached[1] if cached else []

    today    = datetime.now(timezone.utc).date()
    cutoff   = today - timedelta(days=window_days)
    recent   = []
    for t in tournaments:
        try:
            end = datetime.strptime(t.get("endDate", "")[:10], "%Y-%m-%d").date()
        except Exception:
            continue
        # On garde tout tournoi qui s'est terminé après le cutoff (donc actif ou récent)
        if end >= cutoff:
            recent.append(t["id"])
    return recent

async def get_match_games(match_id: str) -> list[dict]:
    """
    Renvoie la liste des games d'un match avec leur résultat.
    Format : [{"map": 1, "winner_team_id": "...", "state": "completed"}, ...]
    """
    try:
        data = await get_event_details(match_id)
        match = data.get("data", {}).get("event", {}).get("match", {})
        games = match.get("games", [])

        result = []
        for g in games:
            game_state = g.get("state", "")
            number     = g.get("number", 0)
            teams      = g.get("teams", [])

            winner_team_id = None
            for t in teams:
                if (t.get("result") or {}).get("outcome") == "win":
                    winner_team_id = t.get("id", "")
                    break

            result.append({
                "map":            number,
                "state":          game_state,
                "winner_team_id": winner_team_id,
            })
        return result
    except Exception:
        return []

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
    if league_id in CURRENT_TOURNAMENT_IDS:
        return CURRENT_TOURNAMENT_IDS[league_id]
    try:
        data   = await get_schedule([league_id])
        events = data.get("data", {}).get("schedule", {}).get("events", [])
        for ev in events:
            tid = ev.get("match", {}).get("tournamentId") or ev.get("tournamentId")
            if tid:
                return tid
    except Exception:
        pass

    try:
        data        = await get_tournaments_for_league(league_id)
        leagues     = data.get("data", {}).get("leagues", [])
        tournaments = []
        for league in leagues:
            tournaments.extend(league.get("tournaments", []))
        if not tournaments:
            return None
        now = datetime.now(timezone.utc).date()
        for t in sorted(tournaments, key=lambda x: x.get("startDate", ""), reverse=True):
            start = t.get("startDate", "")
            end   = t.get("endDate", "")
            try:
                s = datetime.strptime(start[:10], "%Y-%m-%d").date()
                e = datetime.strptime(end[:10],   "%Y-%m-%d").date()
                if s <= now <= e:
                    return t["id"]
            except Exception:
                continue
        past = [t for t in tournaments if t.get("startDate", "9999")[:10] <= now.isoformat()]
        if past:
            return sorted(past, key=lambda t: t.get("startDate", ""), reverse=True)[0]["id"]
        return None
    except Exception:
        return None