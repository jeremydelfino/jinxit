"""
services/gm_resolve.py
Résolution d'un match Myceo : draft (CoachDiff) + force d'équipe + mental → P(win).
+ simulation IA vs IA (base_strength). MVP : force = OVR titulaires vs base_strength,
mental = clutch/stress moyens. (synergie/side/traits + mental-break → couche 2)
"""
import math, random
from sqlalchemy.orm import Session

from models.gm_contract    import GmContract
from models.gm_player_card import GmPlayerCard

# ─── Poids du modèle (tunable) ─────────────────────────────
W_DRAFT, W_STRENGTH, W_MENTAL = 0.45, 0.40, 0.15
K_SIGMOID = 4.0
F_SCALE   = 15.0           # normalisation des écarts d'OVR / strength

# ─── Récompenses budget (tunable) ──────────────────────────
REWARD_BASE, REWARD_WIN = 300, 500


def _sigmoid(x): return 1.0 / (1.0 + math.exp(-x))
def _clamp(x, lo=-1.0, hi=1.0): return max(lo, min(hi, x))


def team_metrics(db: Session, team_id: int):
    """OVR + clutch + stress moyens des 5 titulaires."""
    starters = db.query(GmContract).filter(
        GmContract.team_id == team_id, GmContract.is_starter == True
    ).all()
    if not starters:
        return {"ovr": 60.0, "clutch": 50.0, "stress": 50.0, "n": 0}
    cards = db.query(GmPlayerCard).filter(
        GmPlayerCard.id.in_([c.card_id for c in starters])
    ).all()
    n = len(cards) or 1
    return {"ovr":    sum(c.ovr for c in cards) / n,
            "clutch": sum(c.clutch for c in cards) / n,
            "stress": sum(c.stress for c in cards) / n, "n": n}


def compute_pwin(draft_user, draft_opp, metrics, opp_strength):
    """Retourne (p_win, d, f, m, strength_user, mental_user)."""
    d = _clamp((draft_user - draft_opp) / 100.0)
    strength_user = metrics["ovr"]
    f = _clamp((strength_user - opp_strength) / F_SCALE)
    mental_user = ((metrics["clutch"] - 50.0) + (metrics["stress"] - 50.0)) / 100.0
    m = _clamp(mental_user)
    z = K_SIGMOID * (W_DRAFT * d + W_STRENGTH * f + W_MENTAL * m)
    return _sigmoid(z), d, f, m, strength_user, mental_user


def reward_for(win: bool, importance: float = 1.0) -> int:
    return round((REWARD_BASE + (REWARD_WIN if win else 0)) * importance)


def sim_ai_series(strength_home, strength_away, wins_needed=1):
    """Série IA vs IA → (score_home, score_away, winner_side)."""
    p_home = _sigmoid(K_SIGMOID * (strength_home - strength_away) / F_SCALE)
    sh = sa = 0
    while sh < wins_needed and sa < wins_needed:
        if random.random() < p_home: sh += 1
        else:                        sa += 1
    return sh, sa, ("HOME" if sh > sa else "AWAY")