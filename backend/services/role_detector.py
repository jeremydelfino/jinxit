"""
services/role_detector.py
Détection des rôles via algorithme Hongrois (méthode op.gg / u.gg).

Hiérarchie des signaux (du plus fort au plus faible) :
  1. SMITE = JUNGLE (contrainte dure si exactement 1 Smite dans l'équipe)
  2. Rôle pro officiel    → biais -100 (très fort, mais résoluble si conflit)
  3. Historique récent    → biais -25  (fort)
  4. Score champion×rôle  → table additive (Senna = ADC + Support, l'algo tranche)
  5. Spells (TP, Heal…)   → biais modéré

Le biais "position en champ-select" a été SUPPRIMÉ : Spectator-V5 retourne les
participants dans l'ordre du champ-select (par tour de pick), pas par rôle.
Source: validé sur Riot API docs + comportement observé en SoloQ.
"""
import logging

logger = logging.getLogger(__name__)

TOP, JUNGLE, MID, ADC, SUPPORT = "TOP", "JUNGLE", "MID", "ADC", "SUPPORT"
ROLE_ORDER = [TOP, JUNGLE, MID, ADC, SUPPORT]

ROLE_MAP = {
    "TOP":     TOP,    "JUNGLE":  JUNGLE, "MIDDLE":  MID,    "MID":     MID,
    "BOTTOM":  ADC,    "ADC":     ADC,    "UTILITY": SUPPORT, "SUPPORT": SUPPORT,
}

# ─── Summoner Spell IDs ───────────────────────────────────────
CLEANSE, EXHAUST, FLASH, GHOST, HEAL = 1, 3, 4, 6, 7
SMITE, TP, IGNITE, BARRIER = 11, 12, 14, 21
TP2 = 32  # Unleashed Teleport (rare)

INF = 10_000.0

# ─── Hard locks (rôles exclusifs absolus) ─────────────────────
# Coût plafonné à 15 dans les rôles autorisés, plancher à 90 ailleurs.
HARD_ROLE_LOCKS: dict[str, set[str]] = {
    "Lee Sin": {JUNGLE},  "Nidalee": {JUNGLE},  "Kindred": {JUNGLE},
    "Kha'Zix": {JUNGLE},  "Rek'Sai": {JUNGLE},  "Ivern":   {JUNGLE},
    "Karthus": {JUNGLE, MID},
    "Caitlyn": {ADC},     "Jinx":    {ADC},     "Twitch":  {ADC},
    "Aphelios": {ADC},    "Zeri":    {ADC},
    "Kog'Maw": {ADC, MID}, "Tristana": {ADC, MID},
    "Soraka":  {SUPPORT, TOP}, "Janna":   {SUPPORT}, "Lulu": {SUPPORT, MID},
    "Nami":    {SUPPORT}, "Yuumi":   {SUPPORT}, "Bard":  {SUPPORT},
    "Ornn":    {TOP},
    "Mundo":   {TOP, JUNGLE}, "Dr. Mundo": {TOP, JUNGLE},
}


# ──────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────

def _spell_set(p: dict) -> set[int]:
    return {p.get("spell1Id"), p.get("spell2Id")} - {None}


def _base_cost_from_tags(champ: str, champ_tags: list[str]) -> dict[str, float]:
    """
    Coût de base par rôle dérivé des tags DDragon, en mode ADDITIF.
    Base 50, on RETIRE pour les rôles naturels et on AJOUTE pour les autres.
    Un champion multi-tags accumule les bonus → l'algo Hongrois tranche
    selon les autres signaux (spells, historique, pro_role).

    Échelle finale : ~[5, 95]
    """
    cost = {role: 50.0 for role in ROLE_ORDER}

    is_marksman = "Marksman" in champ_tags
    is_support  = "Support"  in champ_tags
    is_fighter  = "Fighter"  in champ_tags
    is_tank     = "Tank"     in champ_tags
    is_assassin = "Assassin" in champ_tags
    is_mage     = "Mage"     in champ_tags

    # ── Marksman : ADC très naturel ──────────────────────────
    if is_marksman:
        cost[ADC]     -= 35
        cost[MID]     += 5
        cost[TOP]     += 20
        cost[JUNGLE]  += 25
        cost[SUPPORT] += 10  # cas Senna/Ashe support : adouci, pas bloqué

    # ── Support : SUPPORT naturel ────────────────────────────
    if is_support:
        cost[SUPPORT] -= 35
        cost[ADC]     += 25
        cost[TOP]     += 15
        cost[JUNGLE]  += 20

    # ── Mage : MID > TOP > SUPPORT ───────────────────────────
    if is_mage:
        cost[MID]     -= 25
        cost[TOP]     -= 5
        cost[SUPPORT] -= 5   # mages support existent (Lulu, Brand…)
        cost[ADC]     += 15
        cost[JUNGLE]  += 10

    # ── Assassin : MID > JUNGLE ──────────────────────────────
    if is_assassin:
        cost[MID]     -= 25
        cost[JUNGLE]  -= 18
        cost[TOP]     -= 5
        cost[ADC]     += 20
        cost[SUPPORT] += 25

    # ── Fighter : TOP > JUNGLE ───────────────────────────────
    if is_fighter:
        cost[TOP]     -= 25
        cost[JUNGLE]  -= 15
        cost[MID]     -= 5
        cost[ADC]     += 20
        cost[SUPPORT] += 15

    # ── Tank : TOP / SUPPORT / JUNGLE ────────────────────────
    if is_tank:
        cost[TOP]     -= 22
        cost[SUPPORT] -= 18
        cost[JUNGLE]  -= 12
        cost[MID]     += 5
        cost[ADC]     += 25

    # Clamp au cas où
    for role in ROLE_ORDER:
        cost[role] = max(0.0, min(95.0, cost[role]))

    # ── Hard locks (override final) ──────────────────────────
    if champ in HARD_ROLE_LOCKS:
        allowed = HARD_ROLE_LOCKS[champ]
        for role in ROLE_ORDER:
            cost[role] = min(cost[role], 12.0) if role in allowed else max(cost[role], 88.0)

    return cost


def _adjust_cost_with_spells(cost: dict[str, float], spells: set[int], champ_tags: list[str]) -> dict[str, float]:
    """
    Ajustement par summoner spells.
    Note : SMITE est traité en AMONT par `assign_roles` comme contrainte dure
    (sortie du scoring) — on ne le gère plus ici.
    """
    is_marksman = "Marksman" in champ_tags
    is_support  = "Support"  in champ_tags
    is_fighter  = "Fighter"  in champ_tags
    is_tank     = "Tank"     in champ_tags

    # ── HEAL = ADC ou support ────────────────────────────────
    if HEAL in spells:
        if is_marksman:    cost[ADC]     -= 30
        elif is_support:   cost[SUPPORT] -= 30
        else:
            cost[ADC]     -= 15
            cost[SUPPORT] -= 10
        cost[TOP]    += 25
        cost[JUNGLE] += 30
        cost[MID]    += 20

    # ── EXHAUST = support majoritairement ────────────────────
    if EXHAUST in spells:
        cost[SUPPORT] -= 25
        cost[TOP]     += 15
        cost[JUNGLE]  += 25
        cost[MID]     += 10

    # ── TP = top en majorité, mid parfois ────────────────────
    if TP in spells or TP2 in spells:
        if is_fighter or is_tank:
            cost[TOP]    -= 25
            cost[JUNGLE] += 20
        else:
            cost[TOP] -= 15
            cost[MID] -= 5
        cost[SUPPORT] += 15
        cost[ADC]     += 25  # ADC ne prend (presque) jamais TP

    # ── IGNITE = mid/top/support agressif ────────────────────
    if IGNITE in spells:
        if is_support:  cost[SUPPORT] -= 10
        else:
            cost[MID] -= 8
            cost[TOP] -= 6

    # ── BARRIER / CLEANSE = mid ou ADC ───────────────────────
    if BARRIER in spells or CLEANSE in spells:
        cost[MID] -= 10
        cost[ADC] -= 8
        cost[JUNGLE]  += 15
        cost[SUPPORT] += 10

    # ── GHOST = top ou ADC ───────────────────────────────────
    if GHOST in spells:
        if is_marksman: cost[ADC] -= 12
        else:           cost[TOP] -= 10

    return cost


def _adjust_cost_with_history(cost: dict[str, float], history_role: str | None) -> dict[str, float]:
    """Historique récent : signal fort (-25)."""
    if history_role and history_role in ROLE_ORDER:
        cost[history_role] -= 25.0
    return cost


def _adjust_cost_with_pro_role(cost: dict[str, float], pro_role: str | None) -> dict[str, float]:
    """Rôle pro officiel : signal très fort (-100), résoluble par l'algo si conflit."""
    if pro_role and pro_role in ROLE_ORDER:
        cost[pro_role] -= 100.0
    return cost


# ──────────────────────────────────────────────────────────────
# ALGORITHME D'ASSIGNATION
# ──────────────────────────────────────────────────────────────

def _hungarian_brute(cost_matrix: list[list[float]]) -> list[int]:
    """
    Énumération exhaustive des permutations 5×5 = 120 cas.
    Pour n=5 c'est trivial (microsecondes), et c'est garanti optimal
    sans aucun risque de bug d'implémentation Hongrois.
    """
    from itertools import permutations
    n = len(cost_matrix)
    if n == 0: return []
    best_perm  = None
    best_score = float("inf")
    for perm in permutations(range(n)):
        score = sum(cost_matrix[i][perm[i]] for i in range(n))
        if score < best_score:
            best_score = score
            best_perm  = perm
    return list(best_perm) if best_perm else list(range(n))


def assign_roles(
    team:           list[dict],
    champ_tag_map:  dict[str, list] = {},
    history_map:    dict[str, str]  = {},
    pro_role_map:   dict[str, str]  = {},
) -> list[str]:
    """
    Retourne la liste des rôles assignés (même ordre que `team`).

    Algorithme :
      ÉTAGE 1 — Si exactement 1 joueur a Smite : il est JUNGLE (contrainte dure).
                On résout les 4 autres sur 4 rôles → 24 permutations.
      ÉTAGE 2 — Sinon : scoring complet sur les 5 joueurs → 120 permutations.

    Cas "2 Smites" géré : on tombe en étage 2, l'algo choisira le meilleur
    candidat jungle (en général celui dont le champion + historique colle).
    """
    n = len(team)
    if n == 0:
        return []
    if n != 5:
        logger.warning(f"assign_roles: équipe à {n} joueurs (attendu 5)")
        return ROLE_ORDER[:n] + ["FILL"] * max(0, n - 5)

    # ── Pré-calcul : qui a Smite ? ───────────────────────────
    smite_indices = [i for i, p in enumerate(team) if SMITE in _spell_set(p)]

    # ── ÉTAGE 1 : contrainte dure si exactement 1 Smite ──────
    forced_jungle_idx = smite_indices[0] if len(smite_indices) == 1 else None

    # ── Construction de la matrice de coûts ──────────────────
    cost_matrix: list[list[float]] = []
    debug_rows  = []

    for idx, p in enumerate(team):
        champ    = p.get("championName", "")
        tags     = champ_tag_map.get(champ, [])
        spells   = _spell_set(p)
        hist     = history_map.get(p.get("puuid", ""))
        pro_role = pro_role_map.get(p.get("puuid", ""))

        cost = _base_cost_from_tags(champ, tags)
        cost = _adjust_cost_with_spells(cost, spells, tags)
        cost = _adjust_cost_with_history(cost, hist)
        cost = _adjust_cost_with_pro_role(cost, pro_role)

        cost_matrix.append([cost[role] for role in ROLE_ORDER])
        debug_rows.append((champ, tags, spells, hist, pro_role, cost))

    # ── ÉTAGE 1 : application de la contrainte Smite ─────────
    if forced_jungle_idx is not None:
        jungle_col = ROLE_ORDER.index(JUNGLE)
        # Le joueur Smite : INF partout sauf JUNGLE
        for col in range(5):
            cost_matrix[forced_jungle_idx][col] = INF if col != jungle_col else 0.0
        # Les autres joueurs : INF sur JUNGLE (interdit)
        for i in range(5):
            if i != forced_jungle_idx:
                cost_matrix[i][jungle_col] = INF

    # ── Résolution ───────────────────────────────────────────
    col_assignment = _hungarian_brute(cost_matrix)
    result = [ROLE_ORDER[col] if 0 <= col < len(ROLE_ORDER) else "FILL" for col in col_assignment]

    # ── Logs ─────────────────────────────────────────────────
    smite_log = f" [SMITE→idx{forced_jungle_idx} forcé jungle]" if forced_jungle_idx is not None else ""
    if len(smite_indices) > 1:
        smite_log = f" [⚠️ {len(smite_indices)} Smites — scoring libre]"
    logger.info(f"🎯 assign_roles —{smite_log}")
    for (champ, tags, spells, hist, pro_role, cost), role in zip(debug_rows, result):
        cost_str = " ".join(f"{r}:{cost[r]:.0f}" for r in ROLE_ORDER)
        hist_str = f" hist:{hist}" if hist else ""
        pro_str  = f" pro:{pro_role}" if pro_role else ""
        spell_str = f"S{sorted(spells)}" if spells else "S[]"
        logger.info(f"   {champ:15s} → {role:8s} | {spell_str:18s} | {cost_str}{hist_str}{pro_str}")

    return result


# ──────────────────────────────────────────────────────────────
# COMPATIBILITÉ : helpers legacy gardés au cas où
# ──────────────────────────────────────────────────────────────

def _greedy_assign(cost_matrix: list[list[float]]) -> list[int]:
    """Fallback legacy. Plus appelé en interne mais conservé pour rétrocompat."""
    n = len(cost_matrix)
    result    = [-1] * n
    used_cols: set[int] = set()
    pairs = [(cost_matrix[i][j], i, j) for i in range(n) for j in range(n)]
    pairs.sort()
    for _, i, j in pairs:
        if result[i] == -1 and j not in used_cols:
            result[i] = j
            used_cols.add(j)
            if len(used_cols) == n: break
    return result


def _hungarian(cost_matrix: list[list[float]]) -> list[int]:
    """Alias vers la résolution brute-force pour rétrocompat."""
    return _hungarian_brute(cost_matrix)