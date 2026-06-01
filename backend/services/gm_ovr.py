"""
services/gm_ovr.py
OVR dérivé des 6 stats (mental allégé), pondéré par rôle. Ego hors OVR.
+ salaire et valeur de revente dérivés de l'OVR.
"""
ROLE_WEIGHTS = {
    "TOP":     {"laning": 25, "teamfight": 25, "mechanics": 20, "vision": 12, "stress": 8, "clutch": 10},
    "JUNGLE":  {"laning": 18, "teamfight": 21, "mechanics": 21, "vision": 22, "stress": 8, "clutch": 10},
    "MID":     {"laning": 20, "teamfight": 20, "mechanics": 25, "vision": 17, "stress": 8, "clutch": 10},
    "ADC":     {"laning": 20, "teamfight": 25, "mechanics": 29, "vision":  8, "stress": 8, "clutch": 10},
    "SUPPORT": {"laning": 15, "teamfight": 25, "mechanics": 12, "vision": 30, "stress": 8, "clutch": 10},
}


def compute_ovr(role, laning, teamfight, vision, mechanics, stress, clutch) -> int:
    w = ROLE_WEIGHTS.get((role or "").upper(), ROLE_WEIGHTS["MID"])
    total = (laning * w["laning"] + teamfight * w["teamfight"] + vision * w["vision"]
             + mechanics * w["mechanics"] + stress * w["stress"] + clutch * w["clutch"])
    return round(total / 100)


def salary_from_ovr(ovr: int) -> int:
    """/journée — provisoire (équilibrage tranche 3)."""
    return round(20 * (1.10 ** max(0, ovr - 60)))


def resale_value(ovr: int) -> int:
    """Prix de revente fixe par tranche d'OVR."""
    if ovr >= 90: return 8000
    if ovr >= 85: return 3000
    if ovr >= 75: return 800
    return 200