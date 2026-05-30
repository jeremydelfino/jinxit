"""
services/team_pool_scraper.py
Pools + compos réelles par équipe depuis Leaguepedia (ScoreboardPlayers), en IDs DDragon.
"""
from __future__ import annotations
import os, logging, time
from collections import defaultdict
from datetime import datetime, timezone, timedelta

from mwrogue.esports_client import EsportsClient
from database import SessionLocal
from models.team_champion_pool import TeamChampionPool
from models.team_draft         import TeamDraft
from services.champion_naming  import to_ddragon_id

logger = logging.getLogger(__name__)

LP_TEAMS      = {"KC": "Karmine Corp", "G2": "G2 Esports", "T1": "T1"}
LOOKBACK_DAYS = 180
DECAY_DAYS    = 180
MIN_GAMES_W   = 0.5

ROLE_NORM = {"Top": "TOP", "Jungle": "JUNGLE", "Mid": "MID", "Middle": "MID",
             "Bot": "ADC", "ADC": "ADC", "Support": "SUPPORT"}

_client = None
def _get_client():
    global _client
    if _client is None:
        from mwcleric.auth_credentials import AuthCredentials
        u, p = os.environ.get("LEAGUEPEDIA_USERNAME"), os.environ.get("LEAGUEPEDIA_PASSWORD")
        if not u or not p:
            raise RuntimeError("LEAGUEPEDIA_USERNAME / LEAGUEPEDIA_PASSWORD manquants")
        _client = EsportsClient("lol", credentials=AuthCredentials(username=u, password=p))
        logger.info(f"[team_pool] login OK as {u}")
    return _client

def _now():
    return datetime.now(tz=timezone.utc)

def _parse_date(s):
    if not s: return None
    try: return datetime.fromisoformat(s.replace(" ", "T")).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError): return None

def _decay(date, now):
    d = (now - date).total_seconds() / 86400.0
    if d <= 0: return 1.0
    if d >= DECAY_DAYS: return 0.0
    return 1.0 - d / DECAY_DAYS

def _fetch_team(lp_name, since, max_retries=3):
    client = _get_client()
    for attempt in range(max_retries):
        try:
            rows = client.cargo_client.query(
                tables="ScoreboardPlayers",
                fields="GameId=gid,Champion=champ,Role=role,DateTime_UTC=date",
                where=f'Team="{lp_name}" AND DateTime_UTC >= "{since}"',
                order_by="DateTime_UTC DESC",
                limit="max",
            )
            return [dict(r) for r in rows]
        except Exception as e:
            if "ratelimited" in str(e).lower() and attempt < max_retries - 1:
                wait = 30 * (2 ** attempt)
                logger.warning(f"[team_pool] {lp_name} rate limited, attente {wait}s")
                time.sleep(wait); continue
            logger.warning(f"[team_pool] {lp_name} échec : {e}")
            return []
    return []

def refresh_team_pools(sleep_between: float = 12.0) -> dict:
    now   = _now()
    since = (now - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    db    = SessionLocal()
    summary = {}
    try:
        for i, (code, lp) in enumerate(LP_TEAMS.items()):
            rows = _fetch_team(lp, since)

            # Regroupe les 5 joueurs par game
            games: dict[str, dict[str, str]] = defaultdict(dict)
            gdate: dict[str, datetime] = {}
            for r in rows:
                gid   = (r.get("gid") or "").strip()
                lane  = ROLE_NORM.get((r.get("role") or "").strip())
                champ = to_ddragon_id((r.get("champ") or "").strip())
                date  = _parse_date(r.get("date"))
                if not gid or not lane or not champ or not date:
                    continue
                games[gid][lane] = champ
                if gid not in gdate or date > gdate[gid]:
                    gdate[gid] = date

            db.query(TeamDraft).filter(TeamDraft.team_code == code).delete()
            db.query(TeamChampionPool).filter(TeamChampionPool.team_code == code).delete()

            pool_agg = defaultdict(lambda: {"w": 0.0, "last": None})
            n_comps = 0
            for gid, comp in games.items():
                if len(comp) != 5:          # compo incomplète → ignore
                    continue
                w = _decay(gdate[gid], now)
                if w <= 0:
                    continue
                db.add(TeamDraft(team_code=code, game_id=gid, comp=comp,
                                 weight=round(w, 4), played_at=gdate[gid]))
                n_comps += 1
                for lane, champ in comp.items():
                    cell = pool_agg[(lane, champ)]
                    cell["w"] += w
                    if cell["last"] is None or gdate[gid] > cell["last"]:
                        cell["last"] = gdate[gid]

            lane_tot = defaultdict(float)
            for (lane, _), c in pool_agg.items():
                if c["w"] >= MIN_GAMES_W:
                    lane_tot[lane] += c["w"]
            pool_n = 0
            for (lane, champ), c in pool_agg.items():
                if c["w"] < MIN_GAMES_W:
                    continue
                db.add(TeamChampionPool(team_code=code, lane=lane, champion=champ,
                                        weight=round(c["w"] / (lane_tot[lane] or 1.0), 4),
                                        n_games=round(c["w"], 3), last_played=c["last"]))
                pool_n += 1

            db.commit()
            summary[code] = {"rows": len(rows), "comps": n_comps, "pool": pool_n}
            logger.info(f"[team_pool] {code} → {n_comps} compos, {pool_n} entrées pool")
            if i < len(LP_TEAMS) - 1:
                time.sleep(sleep_between)
        return summary
    finally:
        db.close()