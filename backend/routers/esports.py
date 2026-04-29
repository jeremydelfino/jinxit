from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, validator
from database import get_db
from models.user import User
from models.esports_bet import EsportsBet
from models.esports_team_stats import EsportsTeamStats
from models.transaction import Transaction
from deps import get_current_user
from services import lolesports
from datetime import datetime, timezone
from typing import Optional
from services.odds_engine import compute_match_odds as _compute_match_odds
from models.esports_team_rating import EsportsTeamRating
from deps import get_current_user, get_admin_user
import math

router = APIRouter(prefix="/esports", tags=["esports"])

# ─── Config ligues ────────────────────────────────────────────
COVERED_LEAGUES = {
    "lec":    "98767991302996019",
    "lfl":    "105266103462388553", 
    "lck":    "98767991310872058",
    "lcs":    "98767991299243165",
    "lpl":    "98767991314006698",
    "worlds": "98767975604431411",
    "msi":    "98767991325878492",
}

LEAGUE_ID_TO_SLUG = {v: k for k, v in COVERED_LEAGUES.items()}

SCORE_MULTIPLIERS = {
    3: {"2-0": 1.80, "2-1": 1.25},
    5: {"3-0": 2.20, "3-1": 1.60, "3-2": 1.20},
    1: {"1-0": 1.0},
}

# ─── Prior winrates saison 2025 ───────────────────────────────
PRIOR_WINRATES = {
    # LCK 2025
    "T1":   0.78, "GEN":  0.74, "HLE":  0.65, "KT":   0.58,
    "DK":   0.52, "NS":   0.45, "KRX":  0.42, "BRO":  0.35,
    "DNS":  0.30, "BFX":  0.28,
    # LEC 2025
    "G2":   0.88, "FNC":  0.45, "KC":   0.72, "VIT":  0.55,
    "TH":   0.48, "GX":   0.50, "MKOI": 0.65, "SK":   0.38,
    "NAVI": 0.45, "SHFT": 0.32, "LR":   0.40, "KCB":  0.25,
    # LCS 2025
    "C9":   0.70, "TL":   0.65, "NRG":  0.60, "100":  0.55,
    "EG":   0.50, "FLY":  0.48, "DIG":  0.42, "IMT":  0.38,
    # LPL 2025
    "BLG":  0.75, "JDG":  0.72, "NIP":  0.68, "EDG":  0.65,
    "WBG":  0.62, "OMG":  0.55, "LNG":  0.52, "AL":   0.48,

    # LFL 2025
    "VITB": 0.72, "SLY":  0.65, "KCB":  0.62, "GW":   0.55,
    "IJC":  0.50, "JL":   0.48, "ZPR":  0.45, "TLNP": 0.42,
    "GL":   0.40, "BKR":  0.50, "FK":   0.50, "SC":   0.45,
    "LIL":  0.45,
}

# ─── Normalisation league_id → slug interne ──────────────────

def normalize_league_slug(league: dict) -> str:
    league_id = league.get("id", "")
    if league_id in LEAGUE_ID_TO_SLUG:
        return LEAGUE_ID_TO_SLUG[league_id]
    
    raw = league.get("slug", "").lower()
    for slug in COVERED_LEAGUES:
        if raw.startswith(slug):
            return slug
    
    # Fallback sur le name
    name = league.get("name", "").lower()
    if "emea" in name or "lec" in name:      return "lec"
    if "lck" in name or "korea" in name:     return "lck"
    if "lcs" in name:                        return "lcs"
    if "lpl" in name:                        return "lpl"
    if "française" in name or "lfl" in name: return "lfl"
    if "worlds" in name or "world" in name:  return "worlds"
    if "msi" in name:                        return "msi"
    
    return raw

# ─── Winrate bayésien ─────────────────────────────────────────

def get_team_winrate_from_db(team_code: str, league_slug: str, db: Session) -> float:
    """
    Winrate bayésien : mélange données saison courante + prior 2025.
    Fallback chaîné : ligue courante → n'importe quelle ligue → prior → 0.5
    """
    stats = db.query(EsportsTeamStats).filter(
        EsportsTeamStats.team_code   == team_code,
        EsportsTeamStats.league_slug == league_slug,
    ).first()

    if stats:
        return stats.winrate

    # Fallback : même équipe dans une autre ligue (équipe internationale)
    stats_any = db.query(EsportsTeamStats).filter(
        EsportsTeamStats.team_code == team_code,
    ).order_by(EsportsTeamStats.updated_at.desc()).first()

    if stats_any:
        return stats_any.winrate

    return PRIOR_WINRATES.get(team_code, 0.50)

# ─── Refresh standings ────────────────────────────────────────

async def refresh_standings_for_league(league_slug: str, db: Session):
    league_id = COVERED_LEAGUES.get(league_slug)
    if not league_id:
        return

    tournament_id = await lolesports.get_current_tournament_id(league_id)
    if not tournament_id:
        print(f"[standings] {league_slug}: pas de tournament_id trouvé")
        return

    try:
        data      = await lolesports.get_standings(tournament_id)
        standings = data.get("data", {}).get("standings", [])
    except Exception as e:
        print(f"[standings] erreur {league_slug}: {e}")
        return

    updated = 0
    for standing in standings:
        for stage in standing.get("stages", []):
            for section in stage.get("sections", []):
                for ranking in section.get("rankings", []):
                    for team in ranking.get("teams", []):
                        code   = team.get("code", "")
                        record = team.get("record", {})
                        wins   = record.get("wins", 0)
                        losses = record.get("losses", 0)
                        total  = wins + losses

                        # Bayésien : convergence progressive vers les vraies données
                        prior  = PRIOR_WINRATES.get(code, 0.50)
                        weight = min(total / 20.0, 1.0)
                        wr_raw = wins / total if total > 0 else prior
                        wr     = weight * wr_raw + (1 - weight) * prior

                        existing = db.query(EsportsTeamStats).filter(
                            EsportsTeamStats.team_code   == code,
                            EsportsTeamStats.league_slug == league_slug,
                        ).first()

                        if existing:
                            existing.wins          = wins
                            existing.losses        = losses
                            existing.winrate       = wr
                            existing.tournament_id = tournament_id
                            existing.team_image    = team.get("image", existing.team_image)
                            existing.team_name     = team.get("name", existing.team_name)
                        else:
                            db.add(EsportsTeamStats(
                                team_code     = code,
                                team_name     = team.get("name", ""),
                                team_image    = team.get("image", ""),
                                league_slug   = league_slug,
                                tournament_id = tournament_id,
                                wins          = wins,
                                losses        = losses,
                                winrate       = wr,
                            ))
                        updated += 1

    db.commit()
    print(f"[standings] {league_slug}: {updated} équipes mises à jour (tournament: {tournament_id})")


async def refresh_all_standings(db: Session):
    for slug in COVERED_LEAGUES:
        try:
            await refresh_standings_for_league(slug, db)
        except Exception as e:
            print(f"[standings] erreur globale {slug}: {e}")

# ─── Calcul des cotes ─────────────────────────────────────────

def compute_odds(
    amount_team1: int,
    amount_team2: int,
    wr_team1: float,
    wr_team2: float,
    target: str,
    margin: float = 0.85,
) -> float:
    total_wr = wr_team1 + wr_team2
    base_p1  = wr_team1 / total_wr if total_wr > 0 else 0.5
    base_p2  = 1 - base_p1

    total_bets = (amount_team1 or 0) + (amount_team2 or 0)
    if total_bets > 200:
        bet_p1 = (amount_team1 or 0) / total_bets
        bet_p2 = (amount_team2 or 0) / total_bets
        p1 = 0.7 * base_p1 + 0.3 * bet_p1
        p2 = 0.7 * base_p2 + 0.3 * bet_p2
    else:
        p1 = base_p1
        p2 = base_p2

    try:
        raw = (1 / p1) * margin if target == "team1" else (1 / p2) * margin
    except:
        raw = 2.0
    return round(max(1.10, min(4.00, raw)), 2)


def get_bet_amounts(db: Session, match_id: str) -> tuple[int, int]:
    rows = (
        db.query(EsportsBet.bet_value, func.sum(EsportsBet.amount))
        .filter(
            EsportsBet.match_id == match_id,
            EsportsBet.bet_type == "match_winner",
            EsportsBet.status   == "pending",
        )
        .group_by(EsportsBet.bet_value)
        .all()
    )
    amounts = {r[0]: r[1] for r in rows}
    return amounts.get("team1", 0), amounts.get("team2", 0)


def parse_actual_score(t1_wins: int, t2_wins: int) -> tuple[str, str]:
    if t1_wins > t2_wins:
        return "team1", f"{t1_wins}-{t2_wins}"
    return "team2", f"{t2_wins}-{t1_wins}"

# ─── Résolution des paris ─────────────────────────────────────

def resolve_match(match_id: str, db: Session, match_extras: dict | None = None):
    """
    ...
    match_extras : dict optionnel avec des infos pour résoudre les paris avancés.
        - game_winners : ["team1", "team2", "team1"] (gagnants par map)
    """
    if match_extras is None:
        match_extras = {}

    bets = db.query(EsportsBet).filter(
        EsportsBet.match_id == match_id,
        EsportsBet.status   == "pending",
    ).all()
    if not bets:
        return

    sample        = bets[0]
    actual_winner = (sample.actual_winner or "").lower().strip()
    actual_score  = (sample.actual_score  or "").strip()

    if not actual_winner:
        logger.warning(f"[resolve_match] {match_id}: actual_winner vide, abort")
        return

    for bet in bets:
        user = db.query(User).filter(User.id == bet.user_id).first()
        if not user:
            logger.warning(f"[resolve_match] bet {bet.id}: user introuvable")
            continue

        bet_value = (bet.bet_value or "").lower().strip()
        won       = False

        if bet.bet_type == "match_winner":
            won = (bet_value == actual_winner)
        elif bet.bet_type == "exact_score":
            parts      = bet_value.split("_", 1)
            bet_winner = parts[0]
            bet_score  = parts[1] if len(parts) > 1 else ""
            won        = (bet_winner == actual_winner and bet_score == actual_score)

        elif bet.bet_type == "total_maps_over":
            # actual_score = "2-1", "3-0", etc.
            try:
                t1w, t2w = [int(x) for x in actual_score.split("-")]
                threshold = float(bet.bet_value)
                won = (t1w + t2w) > threshold
            except (ValueError, AttributeError):
                logger.warning(f"[resolve_match] bet {bet.id}: actual_score invalide '{actual_score}'")
                continue

        elif bet.bet_type == "total_maps_under":
            try:
                t1w, t2w = [int(x) for x in actual_score.split("-")]
                threshold = float(bet.bet_value)
                won = (t1w + t2w) < threshold
            except (ValueError, AttributeError):
                logger.warning(f"[resolve_match] bet {bet.id}: actual_score invalide '{actual_score}'")
                continue

        elif bet.bet_type == "first_map":
            # Première map = première game qu'on a dans game_winners
            game_winners = match_extras.get("game_winners", [])
            if not game_winners:
                logger.warning(f"[resolve_match] bet {bet.id}: pas de games disponibles, skip")
                continue
            won = (bet_value == game_winners[0])

        elif bet.bet_type == "map_winner":
            game_winners = match_extras.get("game_winners", [])
            parts = bet_value.split("_")
            if len(parts) != 2 or not parts[1].startswith("map"):
                logger.warning(f"[resolve_match] bet {bet.id}: bet_value malformé '{bet_value}'")
                continue
            try:
                map_n = int(parts[1].replace("map", ""))
            except ValueError:
                continue
            if map_n < 1 or map_n > len(game_winners):
                logger.warning(f"[resolve_match] bet {bet.id}: map {map_n} hors limites")
                continue
            won = (parts[0] == game_winners[map_n - 1])

        else:
            logger.warning(f"[resolve_match] bet {bet.id}: type inconnu '{bet.bet_type}', skip")
            continue

        if won:
            payout       = math.floor(bet.amount * (bet.odds or 2.0))
            bet.payout   = payout
            bet.status   = "won"
            user.coins  += payout
            db.add(Transaction(
                user_id=user.id,
                type="bet_won",
                amount=payout,
                description=f"Esports gagné — {sample.team1_code} vs {sample.team2_code} ({bet.bet_value})",
            ))
            logger.info(f"[resolve_match] bet {bet.id}: ✅ WON +{payout} (mise {bet.amount}, odds {bet.odds})")
        else:
            bet.payout = 0
            bet.status = "lost"
            logger.info(f"[resolve_match] bet {bet.id}: ❌ LOST (misait '{bet.bet_value}', gagnant='{actual_winner}')")

        bet.resolved_at = datetime.utcnow()

    db.commit()

# ─── Routes ───────────────────────────────────────────────────

@router.get("/schedule")
async def get_esports_schedule(
    leagues: str = "lec,lck,lcs,lpl,lfl,worlds,msi",
    db: Session = Depends(get_db),
):
    league_slugs = [l.strip().lower() for l in leagues.split(",")]
    league_ids   = [COVERED_LEAGUES[s] for s in league_slugs if s in COVERED_LEAGUES]
    if not league_ids:
        raise HTTPException(400, "Aucune ligue valide")

    try:
        data = await lolesports.get_schedule(list(COVERED_LEAGUES.values()))
    except Exception as e:
        raise HTTPException(502, f"Erreur API LoL Esports : {e}")

    events = data.get("data", {}).get("schedule", {}).get("events", [])

    # ── Récupérer les completed events pour combler la fenêtre + alimenter le moteur de cotes
    completed_extra = {}
    all_completed_for_odds = []   # tous les completed events pour le moteur de cotes

    for slug in league_slugs:
        lid = COVERED_LEAGUES.get(slug)
        if not lid:
            continue
        try:
            tid = await lolesports.get_current_tournament_id(lid)
            if tid:
                ce   = await lolesports.get_completed_events(tid)
                evts = ce.get("data", {}).get("schedule", {}).get("events", [])
                for ev in evts:
                    mid = ev.get("match", {}).get("id", "")
                    if mid:
                        completed_extra[mid] = ev
                all_completed_for_odds.extend(evts)
        except Exception:
            pass

    seen_ids = {ev.get("match", {}).get("id") for ev in events if ev.get("match")}
    for mid, ev in completed_extra.items():
        if mid not in seen_ids:
            events.append(ev)

    result = []
    for ev in events:
        if not ev.get("match"):
            continue
        match    = ev.get("match", {})
        teams    = match.get("teams", [])
        if len(teams) < 2:
            continue

        t1, t2   = teams[0], teams[1]
        match_id = match.get("id", "")
        state    = ev.get("state", "unstarted")
        bo       = match.get("strategy", {}).get("count", 3)
        league   = ev.get("league", {})
        league_s = normalize_league_slug(league)

        t1_wins    = (t1.get("result") or {}).get("gameWins", 0) or 0
        t2_wins    = (t2.get("result") or {}).get("gameWins", 0) or 0
        t1_outcome = (t1.get("result") or {}).get("outcome", None)
        t2_outcome = (t2.get("result") or {}).get("outcome", None)

        # ── Dérivation robuste de l'état réel ──────────────────────
        # Riot marque parfois mal `state`. On déduit l'état des données factuelles.
        derived_state = state
        has_result    = t1_wins > 0 or t2_wins > 0 or t1_outcome in ("win", "loss") or t2_outcome in ("win", "loss")

        if has_result:
            # Si on a un résultat, le match est terminé — peu importe ce que dit `state`
            derived_state = "completed"
        elif state == "unstarted":
            # Pas de résultat mais marqué unstarted → vérifie la date
            raw_start = ev.get("startTime")
            if raw_start:
                try:
                    start_dt = datetime.fromisoformat(raw_start.replace("Z", "+00:00"))
                    age = datetime.now(timezone.utc) - start_dt
                    # Plus de 6h dans le passé sans résultat = match annulé / reporté
                    # → on l'écarte du "à venir" pour ne pas polluer
                    if age > timedelta(hours=6):
                        derived_state = "completed"  # alternative : "cancelled" si tu veux distinguer
                except Exception:
                    pass

        state = derived_state

        t1_wins    = (t1.get("result") or {}).get("gameWins", 0)
        t2_wins    = (t2.get("result") or {}).get("gameWins", 0)
        t1_outcome = (t1.get("result") or {}).get("outcome", None)
        t2_outcome = (t2.get("result") or {}).get("outcome", None)

        # ── Nouveau moteur de cotes ──────────────────────────
        amt_t1, amt_t2 = get_bet_amounts(db, match_id)
        odds_result    = _compute_match_odds(
            t1_code     = t1.get("code", ""),
            t2_code     = t2.get("code", ""),
            league_slug = league_s,
            events      = all_completed_for_odds,
            db          = db,
            amt_t1      = amt_t1,
            amt_t2      = amt_t2,
        )
        odds_t1 = odds_result["odds_t1"]
        odds_t2 = odds_result["odds_t2"]

        # winrate affiché = probabilité calculée par le moteur
        wr_t1_display = round(odds_result["prob_t1"] * 100)
        wr_t2_display = round(odds_result["prob_t2"] * 100)

        total_bets = db.query(func.count(EsportsBet.id)).filter(
            EsportsBet.match_id == match_id,
            EsportsBet.status.in_(["pending", "won", "lost"]),
        ).scalar() or 0

        result.append({
            "match_id":   match_id,
            "state":      state,
            "start_time": ev.get("startTime"),
            "block_name": ev.get("blockName", ""),
            "league":     league,
            "league_slug": league_s,
            "bo":         bo,
            "teams": [
                {
                    "slot":    "team1",
                    "code":    t1.get("code", "?"),
                    "name":    t1.get("name", ""),
                    "image":   t1.get("image", ""),
                    "wins":    t1_wins,
                    "record":  t1.get("record", {}),
                    "outcome": t1_outcome,
                    "odds":    odds_t1,
                    "winrate": wr_t1_display,
                },
                {
                    "slot":    "team2",
                    "code":    t2.get("code", "?"),
                    "name":    t2.get("name", ""),
                    "image":   t2.get("image", ""),
                    "wins":    t2_wins,
                    "record":  t2.get("record", {}),
                    "outcome": t2_outcome,
                    "odds":    odds_t2,
                    "winrate": wr_t2_display,
                },
            ],
            "score_multipliers": SCORE_MULTIPLIERS.get(bo, SCORE_MULTIPLIERS[3]),
            "total_bets": total_bets,
        })

    order = {"inProgress": 0, "unstarted": 1, "completed": 2}
    result.sort(key=lambda m: (
        order.get(m["state"], 3),
        new_date(m.get("start_time")) if m["state"] == "unstarted"
        else -new_date(m.get("start_time"))
    ))

    return result

def new_date(s: Optional[str]) -> float:
    if not s:
        return 0.0
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


@router.get("/live")
async def get_esports_live(db: Session = Depends(get_db)):
    try:
        data = await lolesports.get_schedule(list(COVERED_LEAGUES.values()))
    except Exception as e:
        raise HTTPException(502, f"Erreur API : {e}")

    events = data.get("data", {}).get("schedule", {}).get("events", [])
    result = []
    for ev in events:
        if not ev.get("match"):
            continue
        match  = ev.get("match", {})
        teams  = match.get("teams", [])
        if len(teams) < 2:
            continue
        t1, t2 = teams[0], teams[1]
        league = ev.get("league", {})
        if league.get("id") not in list(COVERED_LEAGUES.values()):
            continue
        result.append({
            "match_id":   match.get("id"),
            "state":      ev.get("state"),
            "start_time": ev.get("startTime"),
            "league":     league,
            "bo":         match.get("strategy", {}).get("count", 3),
            "teams": [
                {
                    "slot": "team1", "code": t1.get("code"),
                    "name": t1.get("name"), "image": t1.get("image"),
                    "wins": (t1.get("result") or {}).get("gameWins", 0),
                },
                {
                    "slot": "team2", "code": t2.get("code"),
                    "name": t2.get("name"), "image": t2.get("image"),
                    "wins": (t2.get("result") or {}).get("gameWins", 0),
                },
            ],
        })
    return result

@router.get("/match/{match_id}")
async def get_match_detail(
    match_id: str,
    db: Session = Depends(get_db),
):
    """
    Renvoie le détail enrichi d'un match : forme, h2h, rosters, breakdown odds,
    cotes pour tous les types de paris disponibles.
    """
    from services.odds_engine import (
        compute_match_odds as _compute_match_odds,
        compute_h2h_detail,
        compute_total_maps_odds,
        compute_map_winner_odds,
    )
    from models.team_form import TeamForm

    # 1. Trouver l'event dans schedule + completed
    try:
        data = await lolesports.get_schedule(list(COVERED_LEAGUES.values()))
    except Exception as e:
        raise HTTPException(502, f"Erreur API : {e}")

    events = data.get("data", {}).get("schedule", {}).get("events", [])
    all_completed = []
    for slug, lid in COVERED_LEAGUES.items():
        try:
            tid = await lolesports.get_current_tournament_id(lid)
            if tid:
                ce = await lolesports.get_completed_events(tid)
                all_completed.extend(ce.get("data", {}).get("schedule", {}).get("events", []))
        except Exception:
            pass

    seen_ids = {ev.get("match", {}).get("id") for ev in events if ev.get("match")}
    for ev in all_completed:
        mid = ev.get("match", {}).get("id")
        if mid and mid not in seen_ids:
            events.append(ev)
            seen_ids.add(mid)

    match_event = next(
        (ev for ev in events if ev.get("match", {}).get("id") == match_id),
        None,
    )
    if not match_event:
        raise HTTPException(404, "Match introuvable")

    match    = match_event.get("match", {})
    teams    = match.get("teams", [])
    if len(teams) < 2:
        raise HTTPException(400, "Données du match incomplètes")

    t1, t2   = teams[0], teams[1]
    bo       = match.get("strategy", {}).get("count", 3)
    state    = match_event.get("state", "unstarted")
    league   = match_event.get("league", {})
    league_s = normalize_league_slug(league)

    # 2. Calcul des cotes de base
    amt_t1, amt_t2 = get_bet_amounts(db, match_id)
    odds_result = _compute_match_odds(
        t1_code     = t1.get("code", ""),
        t2_code     = t2.get("code", ""),
        league_slug = league_s,
        events      = all_completed,
        db          = db,
        amt_t1      = amt_t1,
        amt_t2      = amt_t2,
    )
    odds_t1 = odds_result["odds_t1"]
    odds_t2 = odds_result["odds_t2"]

    # 3. Forme depuis TeamForm
    def _team_form(code: str) -> dict:
        tf = db.query(TeamForm).filter(TeamForm.team_code == code.upper()).first()
        if not tf:
            return {
                "last_5":          "",
                "streak":          0,
                "forme_score":     0.50,
                "last_match_date": None,
            }
        return {
            "last_5":          tf.last_5_results or "",
            "streak":          tf.streak,
            "forme_score":     tf.forme_score,
            "last_match_date": tf.last_match_date.isoformat() if tf.last_match_date else None,
        }

    # 4. Saison depuis EsportsTeamStats
    def _team_season(code: str) -> dict:
        stats = db.query(EsportsTeamStats).filter(
            EsportsTeamStats.team_code   == code.upper(),
            EsportsTeamStats.league_slug == league_s,
        ).first()
        if not stats:
            stats = db.query(EsportsTeamStats).filter(
                EsportsTeamStats.team_code == code.upper()
            ).order_by(EsportsTeamStats.updated_at.desc()).first()
        if not stats:
            return {"wins": 0, "losses": 0, "winrate": 50}
        return {
            "wins":    stats.wins,
            "losses":  stats.losses,
            "winrate": round(stats.winrate * 100),
        }

    # 5. H2H
    h2h = compute_h2h_detail(t1.get("code", ""), t2.get("code", ""), all_completed, max_history=5)

    # 6. Roster (depuis EsportsPlayer + EsportsTeam)
    def _team_roster(code: str) -> list:
        players = db.query(EsportsPlayer).filter(
            EsportsPlayer.team_code == code.upper(),
            EsportsPlayer.is_active == True,
        ).order_by(EsportsPlayer.is_starter.desc()).all()
        return [
            {
                "summoner_name": p.summoner_name,
                "first_name":    p.first_name,
                "last_name":     p.last_name,
                "role":          p.role,
                "photo_url":     p.photo_url,
            }
            for p in players[:5]  # 5 starters
        ]

    # 7. Cotes des nouveaux types
    side_odds = {
        "first_map": {"team1": odds_t1, "team2": odds_t2},
        "total_maps": compute_total_maps_odds(odds_t1, odds_t2, bo),
        "map_winners": compute_map_winner_odds(odds_t1, odds_t2, bo),
    }

    # 8. Total bets sur ce match
    total_bets = db.query(func.count(EsportsBet.id)).filter(
        EsportsBet.match_id == match_id,
        EsportsBet.status.in_(["pending", "won", "lost"]),
    ).scalar() or 0

    return {
        "match_id":   match_id,
        "state":      state,
        "start_time": match_event.get("startTime"),
        "block_name": match_event.get("blockName", ""),
        "league":     {
            "slug":  league_s,
            "name":  league.get("name", ""),
            "image": league.get("image", ""),
        },
        "bo": bo,

        "teams": [
            {
                "slot":    "team1",
                "code":    t1.get("code", ""),
                "name":    t1.get("name", ""),
                "image":   t1.get("image", ""),
                "record":  t1.get("record", {}),
                "outcome": (t1.get("result") or {}).get("outcome"),
                "wins":    (t1.get("result") or {}).get("gameWins", 0),
                "form":    _team_form(t1.get("code", "")),
                "season":  _team_season(t1.get("code", "")),
                "roster":  _team_roster(t1.get("code", "")),
            },
            {
                "slot":    "team2",
                "code":    t2.get("code", ""),
                "name":    t2.get("name", ""),
                "image":   t2.get("image", ""),
                "record":  t2.get("record", {}),
                "outcome": (t2.get("result") or {}).get("outcome"),
                "wins":    (t2.get("result") or {}).get("gameWins", 0),
                "form":    _team_form(t2.get("code", "")),
                "season":  _team_season(t2.get("code", "")),
                "roster":  _team_roster(t2.get("code", "")),
            },
        ],

        "odds": {
            "team1":      odds_t1,
            "team2":      odds_t2,
            "prob_team1": odds_result["prob_t1"],
            "prob_team2": odds_result["prob_t2"],
        },

        "score_multipliers": SCORE_MULTIPLIERS.get(bo, SCORE_MULTIPLIERS[3]),
        "side_odds":         side_odds,
        "head_to_head":      h2h,
        "total_bets":        total_bets,
    }

@router.get("/standings")
async def get_standings_cached(
    league: str = "lec",
    db: Session = Depends(get_db),
):
    stats = (
        db.query(EsportsTeamStats)
        .filter(EsportsTeamStats.league_slug == league.lower())
        .order_by(EsportsTeamStats.winrate.desc())
        .all()
    )
    return [
        {
            "team_code":  s.team_code,
            "team_name":  s.team_name,
            "team_image": s.team_image,
            "wins":       s.wins,
            "losses":     s.losses,
            "winrate":    round(s.winrate * 100),
            "updated_at": s.updated_at,
        }
        for s in stats
    ]


@router.post("/refresh-standings", include_in_schema=False)
async def trigger_refresh_standings(db: Session = Depends(get_db)):
    await refresh_all_standings(db)
    return {"success": True}

VALID_ESPORTS_BET_TYPES = {
    "match_winner", "exact_score",
    "total_maps_over", "total_maps_under",
    "map_winner", "first_map",
}

class PlaceEsportsBetSchema(BaseModel):
    match_id:  str
    bet_type:  str
    bet_value: str
    amount:    int

    @validator("amount")
    def amount_valid(cls, v):
        if v < 10:
            raise ValueError("Mise minimum 10 coins")
        if v > 100_000:
            raise ValueError("Mise maximum 100 000 coins")
        return v

    @validator("bet_type")
    def bet_type_valid(cls, v):
        if v not in VALID_ESPORTS_BET_TYPES:
            raise ValueError(f"bet_type invalide : {v}")
        return v

@router.post("/bets/place")
async def place_esports_bet(
    body: PlaceEsportsBetSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        events = []

        # Fenêtre principale
        data = await lolesports.get_schedule(list(COVERED_LEAGUES.values()))
        events.extend(data.get("data", {}).get("schedule", {}).get("events", []))

        # Completed events de chaque ligue (matchs passés + hors fenêtre principale)
        for slug, lid in COVERED_LEAGUES.items():
            try:
                tid = await lolesports.get_current_tournament_id(lid)
                if tid:
                    ce   = await lolesports.get_completed_events(tid)
                    evts = ce.get("data", {}).get("schedule", {}).get("events", [])
                    events.extend(evts)
            except Exception:
                pass

        # Dédupliquer par match_id
        seen = set()
        unique_events = []
        for ev in events:
            mid = ev.get("match", {}).get("id")
            if mid and mid not in seen:
                seen.add(mid)
                unique_events.append(ev)
        events = unique_events

    except Exception as e:
        print(f"Erreur API LoL Esports: {e}")
        raise HTTPException(502, "Impossible de vérifier le match auprès de Riot")

    all_ids = [ev.get("match", {}).get("id") for ev in events if ev.get("match")]
    print(f"[bets/place] match_id cherché: {body.match_id}")
    print(f"[bets/place] {len(all_ids)} events dispo: {all_ids[:10]}")

    match_event = next(
        (ev for ev in events
         if ev.get("match", {}).get("id") == body.match_id),
        None,
    )

    if not match_event:
        raise HTTPException(404, "Match introuvable ou déjà terminé")
    raw_state = match_event.get("state", "")
    teams_check = match_event.get("match", {}).get("teams", [])
    has_result = False
    if len(teams_check) >= 2:
        for t in teams_check[:2]:
            r = t.get("result") or {}
            if (r.get("gameWins") or 0) > 0 or r.get("outcome") in ("win", "loss"):
                has_result = True
                break

    if raw_state == "completed" or has_result:
        raise HTTPException(400, "Ce match est déjà terminé")

    raw_start = match_event.get("startTime")
    if raw_start:
        try:
            start_dt = datetime.fromisoformat(raw_start.replace("Z", "+00:00"))
            if start_dt < datetime.now(timezone.utc) - timedelta(hours=6):
                raise HTTPException(400, "Ce match a démarré il y a trop longtemps — il est probablement terminé")
        except HTTPException:
            raise
        except Exception:
            pass

    # 3. Extraction des données et FIX du start_time
    match_data = match_event.get("match", {})
    teams = match_data.get("teams", [])
    if len(teams) < 2:
        raise HTTPException(400, "Données du match incomplètes")

    t1, t2 = teams[0], teams[1]
    bo = match_data.get("strategy", {}).get("count", 3)
    league = match_event.get("league", {})
    league_s = normalize_league_slug(league)

    # Extraction sécurisée de la date de début
    raw_start_time = match_event.get("startTime")
    start_time = None
    if raw_start_time:
        try:
            start_time = datetime.fromisoformat(raw_start_time.replace("Z", "+00:00"))
        except Exception:
            start_time = None

    # 4. Vérifications métier (Doublons et Solde)
    existing = db.query(EsportsBet).filter(
        EsportsBet.user_id == current_user.id,
        EsportsBet.match_id == body.match_id,
        EsportsBet.bet_type == body.bet_type,
        EsportsBet.status == "pending",
    ).first()
    if existing:
        raise HTTPException(400, "Tu as déjà un pari en cours sur ce match")

    if current_user.coins < body.amount:
        raise HTTPException(400, "Coins insuffisants")

    # 5. Calcul des cotes dynamiques
    amt_t1, amt_t2 = get_bet_amounts(db, body.match_id)

    # Charger les événements terminés pour nourrir le moteur de cotes
    bet_events = []
    lid = COVERED_LEAGUES.get(league_s)
    if lid:
        try:
            tid = await lolesports.get_current_tournament_id(lid)
            if tid:
                ce = await lolesports.get_completed_events(tid)
                bet_events = ce.get("data", {}).get("schedule", {}).get("events", [])
        except Exception:
            pass

    # Utilisation du moteur de cotes
    odds_result = _compute_match_odds(
        t1_code=t1.get("code", ""),
        t2_code=t2.get("code", ""),
        league_slug=league_s,
        events=bet_events,
        db=db,
        amt_t1=amt_t1,
        amt_t2=amt_t2,
    )

    # 6. Calcul de la cote finale selon le type de pari
    if body.bet_type == "match_winner":
        if body.bet_value not in ("team1", "team2"):
            raise HTTPException(400, "bet_value invalide pour match_winner")
        odds = odds_result["odds_t1"] if body.bet_value == "team1" else odds_result["odds_t2"]
    
    elif body.bet_type == "exact_score":
        parts = body.bet_value.split("_", 1)
        valid_scores = SCORE_MULTIPLIERS.get(bo, SCORE_MULTIPLIERS[3]).keys()
        
        if len(parts) != 2 or parts[0] not in ("team1", "team2") or parts[1] not in valid_scores:
            raise HTTPException(400, f"bet_value invalide pour exact_score (BO{bo})")
        
        bet_winner = parts[0]
        score_key = parts[1]
        
        # Base odds (winner) * Multiplicateur du score
        base_odds = odds_result["odds_t1"] if bet_winner == "team1" else odds_result["odds_t2"]
        score_mult = SCORE_MULTIPLIERS.get(bo, SCORE_MULTIPLIERS[3]).get(score_key, 1.5)
        odds = round(min(15.0, base_odds * score_mult), 2)
    elif body.bet_type == "first_map":
        # Même cote que match_winner pour la map 1
        if body.bet_value not in ("team1", "team2"):
            raise HTTPException(400, "bet_value invalide pour first_map (team1/team2)")
        odds = odds_result["odds_t1"] if body.bet_value == "team1" else odds_result["odds_t2"]

    elif body.bet_type == "map_winner":
        # bet_value : "team1_map1", "team2_map3", etc.
        from services.odds_engine import compute_map_winner_odds
        parts = body.bet_value.split("_")
        if len(parts) != 2 or parts[0] not in ("team1", "team2") or not parts[1].startswith("map"):
            raise HTTPException(400, "bet_value invalide pour map_winner (ex: team1_map2)")
        try:
            map_n = int(parts[1].replace("map", ""))
        except ValueError:
            raise HTTPException(400, "Numéro de map invalide")
        if map_n < 1 or map_n > bo:
            raise HTTPException(400, f"Map {map_n} hors limites pour ce BO{bo}")

        map_odds_list = compute_map_winner_odds(odds_result["odds_t1"], odds_result["odds_t2"], bo)
        target_map = next((m for m in map_odds_list if m["map"] == map_n), None)
        if not target_map:
            raise HTTPException(400, "Map introuvable")
        odds = target_map["team1"] if parts[0] == "team1" else target_map["team2"]

    elif body.bet_type in ("total_maps_over", "total_maps_under"):
        # bet_value : "2.5", "3.5", "4.5"
        from services.odds_engine import compute_total_maps_odds
        try:
            threshold = float(body.bet_value)
        except ValueError:
            raise HTTPException(400, "Seuil invalide (ex: 2.5)")
        total_odds = compute_total_maps_odds(odds_result["odds_t1"], odds_result["odds_t2"], bo)
        key = f"over_{body.bet_value}" if body.bet_type == "total_maps_over" else f"under_{body.bet_value}"
        if key not in total_odds:
            raise HTTPException(400, f"Seuil {threshold} non disponible pour BO{bo}")
        odds = total_odds[key]

    # 7. Création de l'objet Pari
    bet = EsportsBet(
        user_id=current_user.id,
        match_id=body.match_id,
        league_slug=league_s,
        league_name=league.get("name", ""),
        team1_code=t1.get("code", ""),
        team2_code=t2.get("code", ""),
        team1_name=t1.get("name", ""),
        team2_name=t2.get("name", ""),
        team1_image=t1.get("image", ""),
        team2_image=t2.get("image", ""),
        bo_format=bo,
        bet_type=body.bet_type,
        bet_value=body.bet_value,
        amount=body.amount,
        odds=odds,
        status="pending",
        match_start_time=start_time, # Variable maintenant définie
    )

    # Déduction des coins et enregistrement de la transaction
    current_user.coins -= body.amount
    db.add(bet)
    db.add(Transaction(
        user_id=current_user.id,
        type="bet_placed",
        amount=-body.amount,
        description=f"Esports — {t1.get('code')} vs {t2.get('code')} ({league.get('name', '')})",
    ))
    
    db.commit()
    db.refresh(bet)

    return {
        "status": "success",
        "bet_id": bet.id,
        "amount": bet.amount,
        "odds": bet.odds,
        "coins_restants": current_user.coins,
    }

@router.get("/bets/my-bets")
def get_my_esports_bets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bets = (
        db.query(EsportsBet)
        .filter(EsportsBet.user_id == current_user.id)
        .order_by(EsportsBet.created_at.desc())
        .all()
    )
    return [
        {
            "id":              b.id,
            "match_id":        b.match_id,
            "league_name":     b.league_name,
            "league_slug":     b.league_slug,
            "team1_code":      b.team1_code,
            "team2_code":      b.team2_code,
            "team1_name":      b.team1_name,
            "team2_name":      b.team2_name,
            "team1_image":     b.team1_image,
            "team2_image":     b.team2_image,
            "bo_format":       b.bo_format,
            "bet_type":        b.bet_type,
            "bet_value":       b.bet_value,
            "amount":          b.amount,
            "odds":            b.odds,
            "payout":          b.payout,
            "status":          b.status,
            "actual_winner":   b.actual_winner,
            "actual_score":    b.actual_score,
            "match_start_time": b.match_start_time,
            "created_at":      b.created_at,
            "resolved_at":     b.resolved_at,
        }
        for b in bets
    ]


async def resolve_completed_matches(db: Session):
    """
    Parcourt tous les completed events de toutes les ligues et résout les paris pending.
    Robuste aux cas dégénérés : forfait (gameWins=0-0 + outcome="win"), match annulé, etc.
    """
    import logging
    logger = logging.getLogger(__name__)

    total_resolved = 0
    total_skipped  = 0
    total_errors   = 0

    for slug, lid in COVERED_LEAGUES.items():
        try:
            tid = await lolesports.get_current_tournament_id(lid)
            if not tid:
                logger.warning(f"[resolve] {slug}: pas de tournament_id, skip")
                continue

            ce     = await lolesports.get_completed_events(tid)
            events = ce.get("data", {}).get("schedule", {}).get("events", [])
            logger.info(f"[resolve] {slug}: tournament_id={tid}, {len(events)} completed events")

        except Exception as e:
            logger.error(f"[resolve] {slug}: erreur API — {e}")
            total_errors += 1
            continue

        for ev in events:
            if not ev.get("match"):
                continue

            match    = ev.get("match", {})
            match_id = match.get("id", "")
            if not match_id:
                continue

            teams = match.get("teams", [])
            if len(teams) < 2:
                continue

            # Y a-t-il des paris pending pour ce match ?
            pending_count = db.query(EsportsBet).filter(
                EsportsBet.match_id == match_id,
                EsportsBet.status   == "pending",
            ).count()
            if pending_count == 0:
                continue

            logger.info(f"[resolve] match {match_id} a {pending_count} pari(s) pending — résolution")

            t1, t2     = teams[0], teams[1]
            r1         = t1.get("result") or {}
            r2         = t2.get("result") or {}
            t1_wins    = r1.get("gameWins", 0) or 0
            t2_wins    = r2.get("gameWins", 0) or 0
            t1_outcome = (r1.get("outcome") or "").lower()
            t2_outcome = (r2.get("outcome") or "").lower()

            winner = None
            score  = None

            # ── CAS 1 : gameWins valide (cas normal) ────────────
            if t1_wins > 0 or t2_wins > 0:
                winner, score = parse_actual_score(t1_wins, t2_wins)

            # ── CAS 2 : forfait / WO / 1-0 sans gameWins ───────
            elif t1_outcome == "win" and t2_outcome == "loss":
                winner, score = "team1", "1-0"
            elif t2_outcome == "win" and t1_outcome == "loss":
                winner, score = "team2", "1-0"

            # ── CAS 3 : outcome flou — on attend ───────────────
            else:
                logger.warning(
                    f"[resolve] match {match_id}: gameWins=0-0 et outcomes={t1_outcome}/{t2_outcome} "
                    f"— ambiguous, skip (réessai au prochain cycle)"
                )
                total_skipped += 1
                continue

            logger.info(f"[resolve] match {match_id}: winner={winner}, score={score}")

            # Update tous les paris pending de ce match avec le résultat
            db.query(EsportsBet).filter(
                EsportsBet.match_id == match_id,
                EsportsBet.status   == "pending",
            ).update({
                "actual_winner": winner,
                "actual_score":  score,
            })
            db.commit()

            match_extras = {}
            try:
                games = await lolesports.get_match_games(match_id)
                # Map team_id → "team1"/"team2" pour normaliser
                t1_id = teams[0].get("id", "")
                t2_id = teams[1].get("id", "")
                game_winners = []
                for g in games:
                    if g["state"] != "completed":
                        continue
                    if g["winner_team_id"] == t1_id:
                        game_winners.append("team1")
                    elif g["winner_team_id"] == t2_id:
                        game_winners.append("team2")
                if game_winners:
                    match_extras["game_winners"] = game_winners
            except Exception as e:
                logger.warning(f"[resolve] {match_id}: échec récupération games — {e}")

            try:
                resolve_match(match_id, db, match_extras=match_extras)
                total_resolved += 1
                logger.info(f"[resolve] match {match_id}: ✅ résolu")

            except Exception as e:
                logger.error(f"[resolve] match {match_id}: erreur lors du resolve — {e}")
                total_errors += 1

    logger.info(
        f"[resolve] BILAN — résolus: {total_resolved} | skip ambigus: {total_skipped} | "
        f"erreurs: {total_errors}"
    )

class PlaceEsportsBetSchema(BaseModel):
    match_id:  str
    bet_type:  str
    bet_value: str
    amount:    int

    @validator("amount")
    def amount_valid(cls, v):
        if v < 10:
            raise ValueError("Mise minimum 10 coins")
        if v > 100_000:
            raise ValueError("Mise maximum 100 000 coins")
        return v

    @validator("bet_type")
    def bet_type_valid(cls, v):
        if v not in ("match_winner", "exact_score"):
            raise ValueError("bet_type invalide")
        return v

# Ajouter ces imports en haut
from models.esports_team import EsportsTeam
from models.esports_player import EsportsPlayer

# ─── GET /teams ───────────────────────────────────────────────
@router.get("/teams")
def get_esports_teams(
    region: str = None,
    db: Session = Depends(get_db),
):
    q = db.query(EsportsTeam).filter(EsportsTeam.is_active == True)
    if region:
        q = q.filter(EsportsTeam.region == region.upper())
    teams = q.order_by(EsportsTeam.region, EsportsTeam.name).all()
    return [
        {
            "id":           t.id,
            "code":         t.code,
            "name":         t.name,
            "slug":         t.slug,
            "logo_url":     t.logo_url,
            "region":       t.region,
            "accent_color": t.accent_color,
        }
        for t in teams
    ]


# ─── GET /teams/:code ─────────────────────────────────────────
@router.get("/teams/{team_code}")
def get_esports_team(
    team_code: str,
    db: Session = Depends(get_db),
):
    team = db.query(EsportsTeam).filter(
        EsportsTeam.code == team_code.upper()
    ).first()
    if not team:
        raise HTTPException(404, "Équipe introuvable")

    players = db.query(EsportsPlayer).filter(
        EsportsPlayer.team_code == team_code.upper(),
        EsportsPlayer.is_active == True,
    ).order_by(EsportsPlayer.is_starter.desc()).all()

    # Stats via EsportsTeamStats
    stats = db.query(EsportsTeamStats).filter(
        EsportsTeamStats.team_code == team_code.upper()
    ).order_by(EsportsTeamStats.updated_at.desc()).first()

    return {
        "id":           team.id,
        "code":         team.code,
        "name":         team.name,
        "slug":         team.slug,
        "logo_url":     team.logo_url,
        "region":       team.region,
        "accent_color": team.accent_color,
        "stats": {
            "wins":    stats.wins    if stats else 0,
            "losses":  stats.losses  if stats else 0,
            "winrate": round(stats.winrate * 100) if stats else 50,
        } if stats else None,
        "roster": [
            {
                "id":           p.id,
                "api_id":       p.api_id,
                "summoner_name": p.summoner_name,
                "first_name":   p.first_name,
                "last_name":    p.last_name,
                "role":         p.role,
                "photo_url":    p.photo_url,
                "is_starter":   p.is_starter,
                "riot_puuid":   p.riot_puuid,
            }
            for p in players
        ],
    }


# ─── POST /admin/link-player-puuid ────────────────────────────
# Pour lier manuellement le puuid Riot d'un joueur pro à son EsportsPlayer
@router.post("/admin/link-player-puuid")
async def link_player_puuid(
    player_api_id: str,
    game_name:     str,
    tag_line:      str,
    region:        str,
    db: Session = Depends(get_db),
):
    from services.riot import get_account_by_riot_id
    ep = db.query(EsportsPlayer).filter(EsportsPlayer.api_id == player_api_id).first()
    if not ep:
        raise HTTPException(404, "Joueur introuvable")
    try:
        account = await get_account_by_riot_id(game_name, tag_line, region)
        puuid   = account["puuid"]

        # Vérif doublon
        existing = db.query(EsportsPlayer).filter(
            EsportsPlayer.riot_puuid == puuid,
            EsportsPlayer.id         != ep.id,
        ).first()
        if existing:
            raise HTTPException(400, f"Ce puuid est déjà lié à {existing.summoner_name}")

        ep.riot_puuid = puuid

        # Sync vers ProPlayer si existe
        pro = db.query(ProPlayer).filter(ProPlayer.riot_puuid == puuid).first()
        if pro:
            pro.photo_url     = ep.photo_url or pro.photo_url
            pro.team          = ep.team_code or pro.team
            pro.role          = ep.role or pro.role
            pro.region        = ep.region or pro.region
            pro.team_logo_url = db.query(EsportsTeam).filter(
                EsportsTeam.code == ep.team_code
            ).first().logo_url if ep.team_code else pro.team_logo_url

        db.commit()
        return {"success": True, "player": ep.summoner_name, "puuid": puuid[:20] + "..."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, str(e))

@router.post("/admin/sync-photos", include_in_schema=False)
async def trigger_sync_photos():
    from services.esports_sync import sync_photos_to_pro_players
    await sync_photos_to_pro_players()
    return {"success": True}

@router.post("/admin/sync-team-full/{team_identifier}", include_in_schema=False)
async def sync_team_full(team_identifier: str, db: Session = Depends(get_db)):
    """
    Sync complète d'une équipe à partir de son code, slug ou api_id (présents dans esports_teams).
    Pipeline :
      1. Retrouve l'EsportsTeam en DB (par code, slug ou api_id)
      2. Sync roster depuis l'API LolEsports (joueurs + photos)
      3. Cascade vers ProPlayer (photo, logo, accent_color)
      4. Tente de résoudre les riot_puuid manquants via Riot Account-V1 (si summoner_name dispose d'un tag)
    Retourne un résumé du sync.
    """
    from services.esports_sync import sync_team, sync_photos_to_pro_players
    from services.riot import get_account_by_riot_id
    from models.esports_team import EsportsTeam
    from models.esports_player import EsportsPlayer
    from models.pro_player import ProPlayer

    # ── 1. Retrouver l'équipe (par code, slug, ou api_id) ──────────────
    ident = team_identifier.strip()
    et = (
        db.query(EsportsTeam).filter(EsportsTeam.code == ident.upper()).first()
        or db.query(EsportsTeam).filter(EsportsTeam.slug == ident.lower()).first()
        or db.query(EsportsTeam).filter(EsportsTeam.api_id == ident).first()
    )
    if not et:
        raise HTTPException(404, f"Équipe introuvable (essayé code/slug/api_id = {ident})")

    if not et.slug:
        raise HTTPException(400, f"L'équipe {et.code} n'a pas de slug — impossible d'appeler getTeams")

    region = et.region or "LEC"
    summary = {"team_code": et.code, "team_name": et.name, "region": region}

    # ── 2. Sync roster + photos via getTeams ───────────────────────────
    try:
        synced = await sync_team(et.slug, region, db)
        summary["players_synced"] = synced
    except Exception as e:
        raise HTTPException(500, f"Erreur sync_team({et.slug}): {e}")

    # ── 3. Tentative de résolution riot_puuid manquants ────────────────
    # Pour chaque EsportsPlayer de cette team sans riot_puuid, on essaie
    # via Riot Account-V1 si le summoner_name contient un # (game_name#tag)
    eps = db.query(EsportsPlayer).filter(
        EsportsPlayer.team_code == et.code,
        EsportsPlayer.riot_puuid.is_(None),
    ).all()

    resolved, failed = 0, []
    for ep in eps:
        sn = (ep.summoner_name or "").strip()
        if "#" not in sn:
            failed.append({"player": sn, "reason": "no_tag"})
            continue
        try:
            game_name, tag = sn.split("#", 1)
            account = await get_account_by_riot_id(game_name.strip(), tag.strip(), region)
            puuid = account.get("puuid")
            if not puuid:
                failed.append({"player": sn, "reason": "no_puuid_returned"})
                continue
            # Évite collision
            dup = db.query(EsportsPlayer).filter(
                EsportsPlayer.riot_puuid == puuid,
                EsportsPlayer.id != ep.id,
            ).first()
            if dup:
                failed.append({"player": sn, "reason": f"puuid_already_used_by_{dup.summoner_name}"})
                continue
            ep.riot_puuid = puuid
            resolved += 1
        except Exception as e:
            failed.append({"player": sn, "reason": str(e)[:80]})

    db.commit()
    summary["puuid_resolved"] = resolved
    summary["puuid_failed"]   = failed

    # ── 4. Cascade photos/logos vers ProPlayer ─────────────────────────
    await sync_photos_to_pro_players()
    summary["photos_synced"] = "ok"

    return {"success": True, **summary}

@router.post("/admin/sync-team-by-code/{team_code}", include_in_schema=False)
async def sync_team_by_code(team_code: str, db: Session = Depends(get_db)):
    from services.esports_sync import _upsert_team_from_standings
    from models.esports_team_stats import EsportsTeamStats
    stats = db.query(EsportsTeamStats).filter(
        EsportsTeamStats.team_code == team_code.upper()
    ).first()
    if not stats:
        raise HTTPException(404, f"Équipe {team_code} introuvable dans les standings")
    await _upsert_team_from_standings(stats, db)
    return {"success": True, "team": team_code}

@router.post("/bets/{bet_id}/cancel")
def cancel_esports_bet(
    bet_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bet = db.query(EsportsBet).filter(
        EsportsBet.id      == bet_id,
        EsportsBet.user_id == current_user.id,
    ).first()
    if not bet:
        raise HTTPException(404, "Pari introuvable")
    if bet.status != "pending":
        raise HTTPException(400, "Seuls les paris en cours peuvent être annulés")

    bet.status      = "cancelled"
    current_user.coins += bet.amount
    db.add(Transaction(
        user_id=current_user.id,
        type="bet_refunded",
        amount=bet.amount,
        description=f"Pari annulé — {bet.team1_code} vs {bet.team2_code}",
    ))
    db.commit()
    return {"success": True, "refunded": bet.amount}

# ─── GET /admin/ratings ───────────────────────────────────────
@router.get("/admin/ratings")
def get_team_ratings(
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),              # ← sécurisé
):
    ratings = db.query(EsportsTeamRating).order_by(EsportsTeamRating.team_code).all()
    # Compléter avec toutes les équipes connues sans rating
    rated_codes = {r.team_code for r in ratings}
    from services.odds_engine import PRIOR_WINRATES
    all_codes = set(PRIOR_WINRATES.keys())
    missing = [
        {"team_code": code, "manual_boost": 1.0, "notes": None, "updated_at": None}
        for code in sorted(all_codes - rated_codes)
    ]
    return [
        {
            "id":           r.id,
            "team_code":    r.team_code,
            "manual_boost": r.manual_boost,
            "notes":        r.notes,
            "updated_at":   r.updated_at,
        }
        for r in ratings
    ] + missing


# ─── POST /admin/ratings/{team_code} ─────────────────────────
class SetRatingSchema(BaseModel):
    manual_boost: float
    notes:        str | None = None

    @validator("manual_boost")
    def boost_valid(cls, v):
        if not (0.1 <= v <= 3.0):
            raise ValueError("manual_boost doit être entre 0.1 et 3.0")
        return round(v, 2)

@router.post("/admin/ratings/{team_code}")
def set_team_rating(
    team_code: str,
    body:      SetRatingSchema,
    db:        Session = Depends(get_db),
    _:         User = Depends(get_admin_user),      # ← sécurisé
):
    code   = team_code.upper()
    rating = db.query(EsportsTeamRating).filter(
        EsportsTeamRating.team_code == code
    ).first()
    if rating:
        rating.manual_boost = body.manual_boost
        rating.notes        = body.notes
    else:
        rating = EsportsTeamRating(
            team_code    = code,
            manual_boost = body.manual_boost,
            notes        = body.notes,
        )
        db.add(rating)
    db.commit()
    return {"success": True, "team": code, "manual_boost": body.manual_boost}


# ─── GET /admin/odds-preview/{t1}/{t2} ───────────────────────
@router.get("/admin/odds-preview/{t1_code}/{t2_code}")
async def preview_odds(
    t1_code:     str,
    t2_code:     str,
    league_slug: str = "lec",
    db:          Session = Depends(get_db),
):
    from services.odds_engine import compute_match_odds
    lid = COVERED_LEAGUES.get(league_slug.lower())
    events = []
    if lid:
        try:
            tid = await lolesports.get_current_tournament_id(lid)
            if tid:
                ce     = await lolesports.get_completed_events(tid)
                events = ce.get("data", {}).get("schedule", {}).get("events", [])
        except Exception as e:
            print(f"[preview_odds] erreur: {e}")

    # ← DEBUG TEMPORAIRE
    print(f"[preview_odds] lid={lid} tid={tid if lid else None} events={len(events)}")
    t1_events = [ev for ev in events if any(t.get('code') == t1_code.upper() for t in ev.get('match',{}).get('teams',[]))]
    print(f"[preview_odds] events pour {t1_code}: {len(t1_events)}")
    # ← FIN DEBUG

    result = compute_match_odds(
        t1_code     = t1_code.upper(),
        t2_code     = t2_code.upper(),
        league_slug = league_slug.lower(),
        events      = events,
        db          = db,
    )
    return {"t1": t1_code.upper(), "t2": t2_code.upper(), **result}

# ─── Admin : debug + résolution forcée ───────────────────────

@router.get("/bets/pending-debug")
async def debug_pending_esports_bets(db: Session = Depends(get_db)):
    """Liste tous les paris esports encore en pending — pour diagnostiquer."""
    bets = db.query(EsportsBet).filter(EsportsBet.status == "pending").all()
    return [
        {
            "id":         b.id,
            "user_id":    b.user_id,
            "match_id":   b.match_id,
            "team1_code": b.team1_code,
            "team2_code": b.team2_code,
            "bet_value":  b.bet_value,
            "amount":     b.amount,
            "created_at": b.created_at,
        }
        for b in bets
    ]


@router.post("/bets/resolve-pending")
async def force_resolve_pending_esports(db: Session = Depends(get_db)):
    """Force la résolution de tous les paris esports pending. À appeler manuellement si le scheduler rate."""
    resolved_matches = []
    errors           = []

    await resolve_completed_matches(db)

    # Vérifier combien de paris restent pending après résolution
    still_pending = db.query(EsportsBet).filter(EsportsBet.status == "pending").count()

    return {
        "status":        "done",
        "still_pending": still_pending,
    }


@router.post("/bets/resolve-match/{match_id}")
async def force_resolve_match(match_id: str, db: Session = Depends(get_db)):
    """Force la résolution d'un match spécifique par son match_id Riot."""
    pending = db.query(EsportsBet).filter(
        EsportsBet.match_id == match_id,
        EsportsBet.status   == "pending",
    ).all()

    if not pending:
        return {"status": "no_pending", "match_id": match_id}

    # Chercher le résultat dans l'API
    found = False
    for slug, lid in COVERED_LEAGUES.items():
        try:
            tid = await lolesports.get_current_tournament_id(lid)
            if not tid:
                continue
            ce     = await lolesports.get_completed_events(tid)
            events = ce.get("data", {}).get("schedule", {}).get("events", [])
            for ev in events:
                if not ev.get("match"):
                    continue
                m = ev.get("match", {})
                if m.get("id") != match_id:
                    continue

                teams  = m.get("teams", [])
                if len(teams) < 2:
                    continue
                t1, t2  = teams[0], teams[1]
                t1_wins = (t1.get("result") or {}).get("gameWins", 0)
                t2_wins = (t2.get("result") or {}).get("gameWins", 0)

                if t1_wins == 0 and t2_wins == 0:
                    t1_out = (t1.get("result") or {}).get("outcome", "")
                    t2_out = (t2.get("result") or {}).get("outcome", "")
                    if t1_out == "win":
                        winner, score = "team1", "1-0"
                    elif t2_out == "win":
                        winner, score = "team2", "1-0"
                    else:
                        return {"status": "error", "detail": "Impossible de déterminer le gagnant"}
                else:
                    winner, score = parse_actual_score(t1_wins, t2_wins)

                db.query(EsportsBet).filter(
                    EsportsBet.match_id == match_id,
                    EsportsBet.status   == "pending",
                ).update({"actual_winner": winner, "actual_score": score})
                db.commit()
                resolve_match(match_id, db)
                found = True
                return {
                    "status":  "resolved",
                    "match_id": match_id,
                    "winner":  winner,
                    "score":   score,
                    "bets_resolved": len(pending),
                }
        except Exception as e:
            errors = str(e)
            continue

    if not found:
        return {"status": "not_found_in_completed", "match_id": match_id, "detail": "Match pas trouvé dans les completed events"}

@router.get("/debug/completed-events")
async def debug_completed_events(db: Session = Depends(get_db)):
    """Debug : liste tous les match_ids des completed events par ligue."""
    result = {}
    target_ids = {
        "115548668059523652",
        "115548668059589328", 
        "115548668059523684",
        "115548668059523640",
    }
    
    for slug, lid in COVERED_LEAGUES.items():
        try:
            tid = await lolesports.get_current_tournament_id(lid)
            if not tid:
                result[slug] = {"error": "pas de tournament_id"}
                continue
            
            ce     = await lolesports.get_completed_events(tid)
            events = ce.get("data", {}).get("schedule", {}).get("events", [])
            
            match_events = []
            for ev in events:
                if not ev.get("match"):
                    continue
                m      = ev.get("match", {})
                mid    = m.get("id", "")
                teams  = m.get("teams", [])
                t1     = teams[0] if len(teams) > 0 else {}
                t2     = teams[1] if len(teams) > 1 else {}
                match_events.append({
                    "match_id": mid,
                    "found":    mid in target_ids,
                    "t1_code":  t1.get("code"),
                    "t2_code":  t2.get("code"),
                    "t1_wins":  (t1.get("result") or {}).get("gameWins"),
                    "t2_wins":  (t2.get("result") or {}).get("gameWins"),
                    "t1_out":   (t1.get("result") or {}).get("outcome"),
                    "t2_out":   (t2.get("result") or {}).get("outcome"),
                    "state":    ev.get("state"),
                })
            
            found_targets = [e for e in match_events if e["found"]]
            result[slug] = {
                "tournament_id": tid,
                "total_events":  len(match_events),
                "target_matches_found": found_targets,
                "all_match_ids": [e["match_id"] for e in match_events],
            }
        except Exception as e:
            result[slug] = {"error": str(e)}
    
    return result

@router.get("/debug/completed-split2")
async def debug_completed_split2():
    import httpx
    tournament_id = "115548668058343983"  # LEC Split 2
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            "https://esports-api.lolesports.com/persisted/gw/getCompletedEvents",
            headers={"x-api-key": "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"},
            params={"hl": "fr-FR", "tournamentId": tournament_id},
        )
        data   = r.json()
        events = data.get("data", {}).get("schedule", {}).get("events", [])
        return {
            "total": len(events),
            "types": [ev.get("type") for ev in events],
            "first_event": events[0] if events else None,
        }

@router.post("/admin/sync-team/{team_identifier}", include_in_schema=False)
async def sync_team_endpoint(team_identifier: str, db: Session = Depends(get_db)):
    """
    Sync UNE équipe par code, slug ou api_id.
    Ex: POST /esports/admin/sync-team/T1
        POST /esports/admin/sync-team/t1-academy
    """
    from services.esports_sync import sync_one_team_full
    from models.esports_team import EsportsTeam

    ident = team_identifier.strip()
    et = (
        db.query(EsportsTeam).filter(EsportsTeam.code == ident.upper()).first()
        or db.query(EsportsTeam).filter(EsportsTeam.slug == ident.lower()).first()
        or db.query(EsportsTeam).filter(EsportsTeam.api_id == ident).first()
    )
    if not et:
        raise HTTPException(404, f"Équipe introuvable : {ident}")

    summary = await sync_one_team_full(et, db)
    return {"success": not summary.get("errors"), **summary}


@router.post("/admin/sync-all-teams", include_in_schema=False)
async def sync_all_teams_endpoint():
    """
    Trigger manuel du sync hebdo : toutes les équipes en DB.
    Asynchrone côté API — peut prendre 1-3 min selon le nombre d'équipes.
    """
    from services.esports_sync import sync_all_teams_from_db
    return await sync_all_teams_from_db()

@router.post("/admin/sync-team/{team_identifier}", include_in_schema=False)
async def sync_team_endpoint(team_identifier: str, db: Session = Depends(get_db)):
    """
    Sync UNE équipe via Leaguepedia (par code, slug, name ou api_id).
    Ex: POST /esports/admin/sync-team/T1
        POST /esports/admin/sync-team/T1A
    """
    from services.esports_sync import sync_one_team_leaguepedia
    from models.esports_team import EsportsTeam

    ident = team_identifier.strip()
    et = (
        db.query(EsportsTeam).filter(EsportsTeam.code == ident.upper()).first()
        or db.query(EsportsTeam).filter(EsportsTeam.slug == ident.lower()).first()
        or db.query(EsportsTeam).filter(EsportsTeam.name.ilike(ident)).first()
        or db.query(EsportsTeam).filter(EsportsTeam.api_id == ident).first()
    )
    if not et:
        raise HTTPException(404, f"Équipe introuvable : {ident}")

    summary = await sync_one_team_leaguepedia(et, db)
    return {"success": not summary.get("errors"), **summary}


@router.post("/admin/sync-all-teams", include_in_schema=False)
async def sync_all_teams_endpoint():
    """Trigger manuel du sync hebdo via Leaguepedia."""
    from services.esports_sync import sync_all_teams_leaguepedia
    return await sync_all_teams_leaguepedia()