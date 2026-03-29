"""
Moteur de calcul des côtes — Jungle Gap (Version MAX EXTREME)
"""
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from models.esports_team_stats import EsportsTeamStats
from models.esports_team_rating import EsportsTeamRating

logger = logging.getLogger(__name__)

# --- PARAMÈTRES DE POLARISATION ---
MARGIN = 0.92          # Marge bookmaker
EXPONENT = 4         # ÉNORME IMPACT : Transforme un petit avantage en gouffre
MIN_ODDS = 1.01        # Autorise les côtes de ultra-favori (ex: T1 vs BRO)
MAX_ODDS = 25.0        # Autorise les côtes de méga-outsider
# ----------------------------------

PRIOR_WINRATES = {
    # LCK
    "T1":   0.62, "GEN":  0.90, "HLE":  0.65, "KT":   0.58,
    "DK":   0.52, "NS":   0.45, "KRX":  0.42, "BFX":  0.75,
    "DNS":  0.30, "BRO":  0.25,
    # LEC
    "G2":   0.78, "FNC":  0.32, "KC":   0.68, "VIT":  0.55,
    "TH":   0.48, "GX":   0.50, "MKOI": 0.62, "SK":   0.38,
    "NAVI": 0.42, "SHFT": 0.32, "LR":   0.40, "KCB":  0.25,
}

INTL_BONUS = {
    "T1":   0.90, "GEN":  0.85, "BLG":  0.80, "JDG":  0.75,
    "G2":   0.90, "KC":   0.55, "MKOI": 0.55, "TL":   0.52,
}
INTL_DEFAULT = 0.30

WEIGHTS = {
    "winrate_saison":   0.45,
    "forme_recente":    0.25,
    "h2h":              0.10,
    "prior":            0.05,
    "momentum":         0.15,
    "force_opposition": 0.05,
    "intl":             0.05,
}

def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))

def _get_manual_boost(team_code: str, db: Session) -> float:
    rating = db.query(EsportsTeamRating).filter(
        EsportsTeamRating.team_code == team_code.upper()
    ).first()
    return rating.manual_boost if rating else 1.0

def _get_winrate_saison(team_code: str, league_slug: str, db: Session) -> float:
    stats = db.query(EsportsTeamStats).filter(
        EsportsTeamStats.team_code   == team_code,
        EsportsTeamStats.league_slug == league_slug,
    ).first()
    if stats and (stats.wins + stats.losses) >= 3:
        return stats.winrate
    any_stats = db.query(EsportsTeamStats).filter(
        EsportsTeamStats.team_code == team_code
    ).order_by(EsportsTeamStats.updated_at.desc()).first()
    if any_stats:
        return any_stats.winrate
    return PRIOR_WINRATES.get(team_code, 0.50)

def _analyze_completed_events(events: list, team_code: str, opponent_code: str | None = None) -> dict:
    team_matches = []
    h2h_results  = []
    now          = datetime.now(timezone.utc)
    week_ago     = now - timedelta(days=7)

    for ev in events:
        if ev.get("type") != "match": continue
        match = ev.get("match", {})
        teams = match.get("teams", [])
        if len(teams) < 2: continue

        t1, t2 = teams[0], teams[1]
        c1, c2 = t1.get("code", ""), t2.get("code", "")
        if team_code not in (c1, c2): continue

        wins1 = (t1.get("result") or {}).get("gameWins", 0)
        wins2 = (t2.get("result") or {}).get("gameWins", 0)
        if wins1 == 0 and wins2 == 0: continue

        is_team1 = (c1 == team_code)
        team_won = (is_team1 and wins1 > wins2) or (not is_team1 and wins2 > wins1)
        opp_code = c2 if is_team1 else c1

        start_str = ev.get("startTime", "")
        match_dt = None
        if start_str:
            try: match_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            except: pass

        team_matches.append({"won": team_won, "opp_code": opp_code, "date": match_dt})
        if opponent_code and opp_code == opponent_code:
            h2h_results.append(team_won)

    team_matches.sort(key=lambda m: m["date"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    # Forme récente
    recent_5 = team_matches[:5]
    forme = sum(1 for m in recent_5 if m["won"]) / len(recent_5) if recent_5 else 0.50

    # Momentum (Augmenté à 0.08 par win de streak pour plus d'extrêmes)
    streak_val = 0.0
    streak_sign = None
    for m in team_matches[:8]:
        if streak_sign is None: streak_sign = m["won"]
        if m["won"] == streak_sign: streak_val += 1
        else: break
    
    momentum_score = 0.50 + (streak_val * 0.08 if streak_sign else -streak_val * 0.08)
    momentum = _clamp(momentum_score, 0.10, 0.90)

    # Force opposition
    opp_winrates = [PRIOR_WINRATES.get(m["opp_code"], 0.50) for m in team_matches[:8] if m["won"]]
    force_opp = sum(opp_winrates) / len(opp_winrates) if opp_winrates else 0.50

    # Fatigue
    recent_week = sum(1 for m in team_matches if m["date"] and m["date"] >= week_ago)
    fatigue = _clamp(1.0 - max(0, recent_week - 2) * 0.05, 0.80, 1.0)

    # H2H
    h2h = sum(h2h_results) / len(h2h_results) if h2h_results else 0.50

    return {
        "forme": forme, "momentum": momentum, "force_opp": force_opp,
        "fatigue": fatigue, "h2h": h2h, "h2h_count": len(h2h_results),
        "n_matches": len(team_matches), "recent_week": recent_week, "streak": streak_val if streak_sign else -streak_val
    }

def compute_team_score(team_code: str, league_slug: str, opp_code: str, events: list, db: Session) -> dict:
    winrate_saison = _get_winrate_saison(team_code, league_slug, db)
    prior          = PRIOR_WINRATES.get(team_code, 0.50)
    intl           = INTL_BONUS.get(team_code, INTL_DEFAULT)
    manual_boost   = _get_manual_boost(team_code, db)

    analysis  = _analyze_completed_events(events, team_code, opp_code)
    
    # Calcul du score pondéré
    score = (
        winrate_saison * WEIGHTS["winrate_saison"] +
        analysis["forme"] * WEIGHTS["forme_recente"]  +
        analysis["h2h"] * WEIGHTS["h2h"] +
        prior * WEIGHTS["prior"] +
        analysis["momentum"] * WEIGHTS["momentum"] +
        analysis["force_opp"] * WEIGHTS["force_opposition"] +
        intl * WEIGHTS["intl"]
    )

    # Application Fatigue et Boost Manuel
    score_final = score * analysis["fatigue"] * manual_boost

    return {
        "score": score_final,
        "detail": {
            "winrate_saison": round(winrate_saison, 3),
            "forme_recente":  round(analysis["forme"], 3),
            "h2h":            round(analysis["h2h"], 3),
            "h2h_count":      analysis["h2h_count"],
            "prior":          round(prior, 3),
            "momentum":       round(analysis["momentum"], 3),
            "force_opp":      round(analysis["force_opp"], 3),
            "intl":           round(intl, 3),
            "fatigue":        round(analysis["fatigue"], 3),
            "manual_boost":   round(manual_boost, 3),
            "streak":         analysis["streak"],
            "recent_week":    analysis["recent_week"],
            "n_matches":      analysis["n_matches"],
        },
    }

def compute_match_odds(t1_code: str, t2_code: str, league_slug: str, events: list, db: Session, amt_t1: int = 0, amt_t2: int = 0) -> dict:
    r1 = compute_team_score(t1_code, league_slug, t2_code, events, db)
    r2 = compute_team_score(t2_code, league_slug, t1_code, events, db)

    # --- MÉCANISME D'EXTRÊME (POLARISATION) ---
    # On utilise l'exposant pour que l'écart de score devienne un fossé
    s1 = max(r1["score"], 0.01) ** EXPONENT
    s2 = max(r2["score"], 0.01) ** EXPONENT

    p1_base = s1 / (s1 + s2)
    p2_base = s2 / (s1 + s2)

    # Ajustement par les paris (pondération progressive max 15%)
    total_bets = amt_t1 + amt_t2
    if total_bets > 500:
        bet_p1 = amt_t1 / total_bets
        bet_weight = _clamp(total_bets / 10000, 0.0, 0.15)
        p1 = (1 - bet_weight) * p1_base + bet_weight * bet_p1
        p2 = 1 - p1
    else:
        p1, p2 = p1_base, p2_base

    # Calcul des côtes avec marge et clamp large
    odds_t1 = round(_clamp((1 / p1) * MARGIN, MIN_ODDS, MAX_ODDS), 2)
    odds_t2 = round(_clamp((1 / p2) * MARGIN, MIN_ODDS, MAX_ODDS), 2)

    return {
        "odds_t1":   odds_t1,
        "odds_t2":   odds_t2,
        "prob_t1":   round(p1, 3),
        "prob_t2":   round(p2, 3),
        "score_t1":  round(s1, 4),
        "score_t2":  round(s2, 4),
        "detail_t1": r1["detail"],
        "detail_t2": r2["detail"],
    }