import logging

logger = logging.getLogger(__name__)

TOP, JUNGLE, MID, ADC, SUPPORT = "TOP", "JUNGLE", "MID", "ADC", "SUPPORT"
ROLE_ORDER = [TOP, JUNGLE, MID, ADC, SUPPORT]

ROLE_MAP = {
    "TOP":     TOP,
    "JUNGLE":  JUNGLE,
    "MIDDLE":  MID,
    "MID":     MID,
    "BOTTOM":  ADC,
    "ADC":     ADC,
    "UTILITY": SUPPORT,
    "SUPPORT": SUPPORT,
}

CLEANSE, EXHAUST, FLASH, GHOST, HEAL, SMITE, TP, TP2, IGNITE, BARRIER = 1, 3, 4, 6, 7, 11, 12, 32, 14, 21


def _role_scores(
    p: dict,
    champ_tags: list[str] = [],
    history_role: str | None = None,
) -> dict[str, float]:
    sp     = {p.get("spell1Id"), p.get("spell2Id")} - {None}
    scores = {role: 0.0 for role in ROLE_ORDER}

    # ── Score de base par tag ─────────────────────────────────
    if "Marksman" in champ_tags:
        scores[ADC] += 15.0
    if "Support" in champ_tags and "Fighter" not in champ_tags and "Mage" not in champ_tags:
        scores[SUPPORT] += 15.0
    if "Support" in champ_tags and "Mage" in champ_tags:
        scores[SUPPORT] += 10.0
        scores[MID]     +=  5.0
    if "Fighter" in champ_tags and "Assassin" not in champ_tags:
        scores[TOP]    += 10.0
        scores[JUNGLE] +=  5.0
    if "Fighter" in champ_tags and "Assassin" in champ_tags:
        scores[JUNGLE] += 8.0
        scores[TOP]    += 6.0
        scores[MID]    += 4.0
    if "Tank" in champ_tags and "Fighter" not in champ_tags:
        scores[SUPPORT] += 8.0
        scores[TOP]     += 6.0
    if "Assassin" in champ_tags and "Fighter" not in champ_tags:
        scores[MID]    += 10.0
        scores[JUNGLE] +=  7.0
    if "Mage" in champ_tags and "Support" not in champ_tags:
        scores[MID] += 12.0

    # ── Summoner Spells ───────────────────────────────────────
    if SMITE in sp:
        scores[JUNGLE] += 100.0

    if EXHAUST in sp:
        scores[SUPPORT] += 30.0
        scores[ADC]     +=  2.0

    if BARRIER in sp or CLEANSE in sp:
        scores[MID] += 10.0
        scores[ADC] +=  8.0

    if HEAL in sp:
        if "Marksman" in champ_tags:
            scores[ADC]     += 40.0
        elif "Support" in champ_tags:
            scores[SUPPORT] += 40.0
        else:
            scores[ADC]     += 20.0
            scores[SUPPORT] += 15.0

    if TP in sp or TP2 in sp:
        if "Fighter" in champ_tags or "Tank" in champ_tags:
            scores[TOP] += 25.0
        elif "Mage" in champ_tags and "Support" not in champ_tags:
            scores[MID] += 20.0
        elif "Support" in champ_tags:
            scores[SUPPORT] += 10.0
            scores[MID]     +=  5.0
        else:
            scores[TOP] += 15.0
            scores[MID] +=  5.0

    if GHOST in sp:
        if "Marksman" in champ_tags:
            scores[ADC] += 20.0
        elif "Fighter" in champ_tags or "Tank" in champ_tags:
            scores[TOP] += 15.0
        else:
            scores[ADC] += 8.0
            scores[TOP] += 6.0

    if IGNITE in sp:
        if "Support" in champ_tags and "Fighter" not in champ_tags:
            scores[SUPPORT] += 15.0
        elif "Mage" in champ_tags or "Assassin" in champ_tags:
            scores[MID]     += 15.0
        elif "Fighter" in champ_tags:
            scores[TOP]     += 12.0
        else:
            scores[SUPPORT] += 5.0
            scores[MID]     += 8.0
            scores[TOP]     += 4.0

    # ── Boost historique ─────────────────────────────────────
    if history_role and history_role in scores:
        scores[history_role] += 20.0

    # ── Plancher asymétrique ──────────────────────────────────
    is_marksman = "Marksman" in champ_tags
    is_support  = "Support" in champ_tags and "Fighter" not in champ_tags

    if scores[ADC] < 2.0 and not is_marksman:
        scores[ADC] = 0.1
    if scores[SUPPORT] < 2.0 and not is_support:
        scores[SUPPORT] = 0.1
    if scores[TOP] < 1.0:
        scores[TOP] = 1.0
    if scores[MID] < 1.0:
        scores[MID] = 1.0
    if scores[JUNGLE] < 0.5:
        scores[JUNGLE] = 0.5

    champ_name = p.get("championName", "?")
    hist_str   = f" [hist:{history_role}]" if history_role else ""
    print(
        f"  📊 {champ_name:15s}{hist_str} | spells={sorted(sp)} | tags={champ_tags} | "
        f"scores={{ {', '.join(f'{r}:{v:.0f}' for r, v in scores.items())} }}"
    )

    return scores


def assign_roles(
    team: list[dict],
    champ_tag_map: dict[str, list] = {},
    history_map:   dict[str, str]  = {},
) -> list[str]:
    n = len(team)
    if n == 0:
        return []

    print("🎯 assign_roles — début")

    score_matrix = [
        _role_scores(
            p,
            champ_tags   = champ_tag_map.get(p.get("championName", ""), []),
            history_role = history_map.get(p.get("puuid", "")),
        )
        for p in team
    ]

    roles_to_assign = ROLE_ORDER[:n]
    best_score      = -1.0
    best_assignment: list[str] = []

    def backtrack(idx, current_roles, current_score, current_assignment):
        nonlocal best_score, best_assignment
        if idx == n:
            if current_score > best_score:
                best_score      = current_score
                best_assignment = list(current_assignment)
            return
        for i, role in enumerate(current_roles):
            remaining = current_roles[:i] + current_roles[i+1:]
            current_assignment.append(role)
            backtrack(idx + 1, remaining, current_score + score_matrix[idx][role], current_assignment)
            current_assignment.pop()

    backtrack(0, roles_to_assign, 0.0, [])

    result = list(zip([p.get("championName", "?") for p in team], best_assignment))
    print(f"✅ assign_roles — résultat: {result} (score={best_score:.1f})")

    return best_assignment