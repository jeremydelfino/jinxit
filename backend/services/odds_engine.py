"""
Moteur de calcul des côtes — Jungle Gap (Version MAX EXTREME)
"""
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from models.esports_team_stats import EsportsTeamStats
from models.esports_team_rating import EsportsTeamRating
from models.team_form import TeamForm

logger = logging.getLogger(__name__)

# --- PARAMÈTRES DE POLARISATION (calibrés 2026) ---
MARGIN   = 0.95  
EXPONENT = 2.5   
MIN_ODDS = 1.20   
MAX_ODDS = 29.0   
# --------------------------------------------------

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
    "G2":   0.90, "KC":   0.55, "MKOI": 0.35, "TL":   0.52,
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

def _get_team_form_from_db(team_code: str, db: Session) -> dict | None:
    """
    Lit TeamForm pour avoir forme_score et streak sans recalculer.
    Retourne None si pas de data → fallback sur _analyze_completed_events.
    """
    tf = db.query(TeamForm).filter(TeamForm.team_code == team_code.upper()).first()
    if not tf:
        return None
    # Conversion streak → momentum [0.10, 0.90] (même mapping que _analyze)
    momentum = _clamp(0.50 + (tf.streak * 0.08), 0.10, 0.90)
    return {
        "forme":    tf.forme_score,
        "momentum": momentum,
        "streak":   tf.streak,
        "last_5":   tf.last_5_results,
    }

def compute_team_score(team_code: str, league_slug: str, opp_code: str, events: list, db: Session) -> dict:
    winrate_saison = _get_winrate_saison(team_code, league_slug, db)
    prior          = PRIOR_WINRATES.get(team_code, 0.50)
    intl           = INTL_BONUS.get(team_code, INTL_DEFAULT)
    manual_boost   = _get_manual_boost(team_code, db)

    analysis  = _analyze_completed_events(events, team_code, opp_code)

    db_form = _get_team_form_from_db(team_code, db)
    if db_form:
        analysis["forme"]    = db_form["forme"]
        analysis["momentum"] = db_form["momentum"]
        analysis["streak"]   = db_form["streak"]
    
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

# ──────────────────────────────────────────────────────────────
# H2H DÉTAILLÉ (pour la fiche match)
# ──────────────────────────────────────────────────────────────

def compute_h2h_detail(t1_code: str, t2_code: str, events: list, max_history: int = 5) -> dict:
    """
    Renvoie l'historique détaillé des confrontations directes entre t1 et t2.
    Retourne total_matches, t1_wins, t2_wins, last_match (date/winner/score) et history.
    """
    h2h_matches = []
    for ev in events:
        if ev.get("type") != "match":
            continue
        match = ev.get("match", {})
        teams = match.get("teams", [])
        if len(teams) < 2:
            continue

        a, b = teams[0], teams[1]
        ca, cb = a.get("code", ""), b.get("code", "")
        # Vérifie qu'on a bien les deux équipes (dans n'importe quel ordre)
        if {ca, cb} != {t1_code, t2_code}:
            continue

        wa = (a.get("result") or {}).get("gameWins", 0)
        wb = (b.get("result") or {}).get("gameWins", 0)
        if wa == 0 and wb == 0:
            continue  # match non joué ou annulé

        # Normalise pour que t1 soit toujours référent
        is_t1_first = (ca == t1_code)
        t1_wins = wa if is_t1_first else wb
        t2_wins = wb if is_t1_first else wa
        winner = "team1" if t1_wins > t2_wins else "team2"

        start_str = ev.get("startTime", "")
        match_dt = None
        if start_str:
            try:
                match_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            except Exception:
                pass

        h2h_matches.append({
            "date":       start_str,
            "date_obj":   match_dt,
            "winner":     winner,
            "score":      f"{t1_wins}-{t2_wins}",
            "t1_wins":    t1_wins,
            "t2_wins":    t2_wins,
        })

    h2h_matches.sort(
        key=lambda m: m["date_obj"] or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    t1_total_wins = sum(1 for m in h2h_matches if m["winner"] == "team1")
    t2_total_wins = sum(1 for m in h2h_matches if m["winner"] == "team2")

    # Nettoie le date_obj (non sérialisable JSON)
    history = []
    for m in h2h_matches[:max_history]:
        history.append({
            "date":   m["date"],
            "winner": m["winner"],
            "score":  m["score"],
        })

    return {
        "total_matches": len(h2h_matches),
        "team1_wins":    t1_total_wins,
        "team2_wins":    t2_total_wins,
        "last_match":    history[0] if history else None,
        "history":       history,
    }


# ──────────────────────────────────────────────────────────────
# CÔTES DES NOUVEAUX TYPES DE PARIS
# ──────────────────────────────────────────────────────────────

MARGIN_SIDE = 0.92  # marge bookmaker pour les paris side


def compute_total_maps_odds(odds_t1: float, odds_t2: float, bo: int) -> dict:
    """
    "Total de maps over/under". Estime la prob qu'on aille au-delà du seuil
    en fonction de la dominance du favori (cotes).
    
    BO3 : seuil = 2.5 (over = match va au game 3 = 2-1 ou 1-2)
    BO5 : seuils = 3.5 et 4.5
    """
    if bo == 1:
        return {}  # pas de "total maps" en BO1

    # Probabilité implicite que le favori gagne (sans la marge)
    prob_t1 = 1.0 / odds_t1 if odds_t1 > 0 else 0.5
    prob_t2 = 1.0 / odds_t2 if odds_t2 > 0 else 0.5
    total_p = prob_t1 + prob_t2
    prob_t1_norm = prob_t1 / total_p if total_p > 0 else 0.5

    # Plus le match est équilibré (prob ≈ 0.5), plus on a de chances d'aller loin
    balance = 1.0 - 2.0 * abs(prob_t1_norm - 0.5)  # 1 si 50/50, 0 si stomp total

    if bo == 3:
        # Prob d'aller au game 3 = corrélée à l'équilibre
        # Match équilibré → ~70% d'aller au 3e game ; stomp → ~25%
        prob_over_2_5 = 0.25 + 0.45 * balance
        odds_over     = round(_clamp(MARGIN_SIDE / prob_over_2_5,        1.20, 5.0), 2)
        odds_under    = round(_clamp(MARGIN_SIDE / (1 - prob_over_2_5),  1.20, 5.0), 2)
        return {
            "over_2.5":  odds_over,
            "under_2.5": odds_under,
        }

    if bo == 5:
        # Prob d'aller au game 4
        prob_over_3_5 = 0.35 + 0.45 * balance
        # Prob d'aller au game 5 (toujours plus rare que game 4)
        prob_over_4_5 = 0.15 + 0.30 * balance
        return {
            "over_3.5":  round(_clamp(MARGIN_SIDE / prob_over_3_5,       1.20, 5.0), 2),
            "under_3.5": round(_clamp(MARGIN_SIDE / (1 - prob_over_3_5), 1.20, 5.0), 2),
            "over_4.5":  round(_clamp(MARGIN_SIDE / prob_over_4_5,       1.20, 6.0), 2),
            "under_4.5": round(_clamp(MARGIN_SIDE / (1 - prob_over_4_5), 1.20, 5.0), 2),
        }

    return {}


def compute_map_winner_odds(odds_t1: float, odds_t2: float, bo: int) -> list:
    """
    Cote pour "qui gagne la map N". La map 1 = même cote que match_winner.
    Les maps suivantes convergent légèrement vers 2.0 (incertitude croissante,
    adaptation des équipes au draft adverse).
    """
    if bo == 1:
        return []

    result = []
    max_maps = bo  # BO3 → 3 maps, BO5 → 5 maps
    for map_n in range(1, max_maps + 1):
        convergence = (map_n - 1) * 0.10  # 0% map1, 10% map2, 20% map3...
        new_t1 = round(_clamp(odds_t1 * (1 - convergence) + 2.0 * convergence, 1.10, 8.0), 2)
        new_t2 = round(_clamp(odds_t2 * (1 - convergence) + 2.0 * convergence, 1.10, 8.0), 2)
        result.append({
            "map":   map_n,
            "team1": new_t1,
            "team2": new_t2,
        })
    return result

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

def compute_handicap_odds(odds_t1: float, odds_t2: float, bo: int) -> list:
    """
    Cotes handicap maps. Le favori part avec un déficit de maps, l'outsider avec une avance.

    BO3 :
      - team1 -1.5 : team1 doit gagner 2-0 (sweep)
      - team1 +1.5 : team1 perd au pire 1-2 (= ne se fait pas sweep)
    BO5 :
      - team1 -1.5 : team1 gagne 3-0 ou 3-1
      - team1 -2.5 : team1 gagne 3-0 (sweep)
      - team1 +1.5 : team1 perd au pire 2-3
      - team1 +2.5 : team1 perd au pire 1-3 (= pas sweep)

    Approche : on dérive de prob_t1 (1/odds_t1 normalisé) la prob de chaque scénario
    via un modèle simple où chaque map = même prob (indépendance).
    """
    if bo == 1:
        return []

    # Probas implicites par map (sans marge)
    inv_t1 = 1.0 / max(odds_t1, 0.01)
    inv_t2 = 1.0 / max(odds_t2, 0.01)
    p1 = inv_t1 / (inv_t1 + inv_t2)
    p2 = 1.0 - p1

    result = []

    if bo == 3:
        # P(2-0 t1) = p1^2 ; P(2-1 t1) = 2*p1^2*p2 ; idem pour t2
        p_2_0_t1 = p1 ** 2
        p_2_1_t1 = 2 * (p1 ** 2) * p2
        p_2_0_t2 = p2 ** 2
        p_2_1_t2 = 2 * (p2 ** 2) * p1

        # team1 -1.5 = team1 gagne 2-0
        # team1 +1.5 = team1 ne perd pas 0-2 (= gagne ou perd 1-2)
        prob_t1_minus = p_2_0_t1
        prob_t1_plus  = p_2_0_t1 + p_2_1_t1 + p_2_1_t2  # tout sauf 2-0 pour t2
        prob_t2_minus = p_2_0_t2
        prob_t2_plus  = p_2_0_t2 + p_2_1_t2 + p_2_1_t1

        result.append({
            "handicap": "-1.5",
            "team1": round(_clamp(MARGIN_SIDE / max(prob_t1_minus, 0.01), 1.20, 8.0), 2),
            "team2": round(_clamp(MARGIN_SIDE / max(prob_t2_minus, 0.01), 1.20, 8.0), 2),
        })
        result.append({
            "handicap": "+1.5",
            "team1": round(_clamp(MARGIN_SIDE / max(prob_t1_plus, 0.01), 1.10, 5.0), 2),
            "team2": round(_clamp(MARGIN_SIDE / max(prob_t2_plus, 0.01), 1.10, 5.0), 2),
        })
        return result

    if bo == 5:
        # P(3-0) = p^3 ; P(3-1) = 3*p^3*q ; P(3-2) = 6*p^3*q^2
        p_3_0_t1 = p1 ** 3
        p_3_1_t1 = 3 * (p1 ** 3) * p2
        p_3_2_t1 = 6 * (p1 ** 3) * (p2 ** 2)
        p_3_0_t2 = p2 ** 3
        p_3_1_t2 = 3 * (p2 ** 3) * p1
        p_3_2_t2 = 6 * (p2 ** 3) * (p1 ** 2)

        # -1.5 = gagne 3-0 ou 3-1 ; +1.5 = perd au pire 2-3 (= pas 0-3 ni 1-3)
        # -2.5 = gagne 3-0 ;       +2.5 = perd au pire 1-3 (= pas 0-3)
        prob_t1_m15 = p_3_0_t1 + p_3_1_t1
        prob_t1_p15 = p_3_0_t1 + p_3_1_t1 + p_3_2_t1 + p_3_2_t2  # tout sauf 0-3 et 1-3 t2
        prob_t1_m25 = p_3_0_t1
        prob_t1_p25 = 1.0 - p_3_0_t2  # tout sauf sweep par t2

        prob_t2_m15 = p_3_0_t2 + p_3_1_t2
        prob_t2_p15 = p_3_0_t2 + p_3_1_t2 + p_3_2_t2 + p_3_2_t1
        prob_t2_m25 = p_3_0_t2
        prob_t2_p25 = 1.0 - p_3_0_t1

        result.append({
            "handicap": "-1.5",
            "team1": round(_clamp(MARGIN_SIDE / max(prob_t1_m15, 0.01), 1.20, 6.0), 2),
            "team2": round(_clamp(MARGIN_SIDE / max(prob_t2_m15, 0.01), 1.20, 6.0), 2),
        })
        result.append({
            "handicap": "+1.5",
            "team1": round(_clamp(MARGIN_SIDE / max(prob_t1_p15, 0.01), 1.10, 4.0), 2),
            "team2": round(_clamp(MARGIN_SIDE / max(prob_t2_p15, 0.01), 1.10, 4.0), 2),
        })
        result.append({
            "handicap": "-2.5",
            "team1": round(_clamp(MARGIN_SIDE / max(prob_t1_m25, 0.01), 1.30, 10.0), 2),
            "team2": round(_clamp(MARGIN_SIDE / max(prob_t2_m25, 0.01), 1.30, 10.0), 2),
        })
        result.append({
            "handicap": "+2.5",
            "team1": round(_clamp(MARGIN_SIDE / max(prob_t1_p25, 0.01), 1.05, 3.0), 2),
            "team2": round(_clamp(MARGIN_SIDE / max(prob_t2_p25, 0.01), 1.05, 3.0), 2),
        })
        return result

    return []