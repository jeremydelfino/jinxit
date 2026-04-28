"""
services/role_detector.py
Détection des rôles via algorithme Hongrois (méthode op.gg / u.gg).

Principe :
  1. Pour chaque (joueur, rôle), on calcule un COÛT (plus c'est bas, plus le
     joueur est légitime à ce rôle).
  2. On résout l'assignation optimale qui minimise la somme des coûts —
     garantissant qu'on a exactement 1 joueur par rôle, sans doublon.
  3. Override Smite : si un joueur a Smite, il est forcément jungler (coût ∞
     partout sauf JUNGLE).

Sources de signal :
  - Tags du champion (DDragon)
  - Summoner spells (Smite, TP, Heal, Exhaust, Ignite…)
  - Historique récent du joueur (rôle le plus joué sur les 20 dernières games)
  - Position en champ-select (les pros respectent l'ordre TOP-JGL-MID-BOT-SUP)

Référence : Munkres / Hungarian assignment, scipy.optimize.linear_sum_assignment
"""
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

# ─── Summoner Spell IDs ───────────────────────────────────────
CLEANSE, EXHAUST, FLASH, GHOST, HEAL = 1, 3, 4, 6, 7
SMITE, TP, IGNITE, BARRIER = 11, 12, 14, 21
TP2 = 32  # Unleashed Teleport (rare, kept for safety)

# ─── Coût "infini" (forçage)  ─────────────────────────────────
INF = 10_000.0

# ─── Champions hardcodés (override pour cas dégénérés) ────────
# Les champions qui ne se jouent QUE dans certains rôles, peu importe le contexte
HARD_ROLE_LOCKS: dict[str, set[str]] = {
    # Junglers exclusifs
    "Lee Sin":   {JUNGLE},
    "Nidalee":   {JUNGLE},
    "Kindred":   {JUNGLE},
    "Kha'Zix":   {JUNGLE},
    "Rek'Sai":   {JUNGLE},
    "Ivern":     {JUNGLE},
    "Karthus":   {JUNGLE, MID},
    # ADC exclusifs
    "Caitlyn":   {ADC},
    "Jinx":      {ADC},
    "Kog'Maw":   {ADC, MID},
    "Tristana":  {ADC, MID},
    "Twitch":    {ADC},
    "Aphelios":  {ADC},
    "Zeri":      {ADC},
    # Support exclusifs (vraiment)
    "Soraka":    {SUPPORT, TOP},
    "Janna":     {SUPPORT},
    "Lulu":      {SUPPORT, MID},
    "Nami":      {SUPPORT},
    "Yuumi":     {SUPPORT},
    "Bard":      {SUPPORT},
    # Tops exclusifs
    "Ornn":      {TOP},
    "Mundo":     {TOP, JUNGLE},
    "Dr. Mundo": {TOP, JUNGLE},
}


def _spell_set(p: dict) -> set[int]:
    return {p.get("spell1Id"), p.get("spell2Id")} - {None}


def _base_cost_from_tags(champ: str, champ_tags: list[str]) -> dict[str, float]:
    """
    Coût de base par rôle, dérivé des tags du champion.
    Plus le coût est bas, plus le rôle est naturel pour ce champion.
    Échelle : [0, 100]
    """
    cost = {role: 50.0 for role in ROLE_ORDER}

    is_marksman = "Marksman" in champ_tags
    is_support  = "Support"  in champ_tags
    is_fighter  = "Fighter"  in champ_tags
    is_tank     = "Tank"     in champ_tags
    is_assassin = "Assassin" in champ_tags
    is_mage     = "Mage"     in champ_tags

    # Marksman → ADC très naturel, autres très coûteux
    if is_marksman:
        cost[ADC]     = 5.0
        cost[MID]     = 60.0
        cost[TOP]     = 80.0
        cost[JUNGLE]  = 85.0
        cost[SUPPORT] = 70.0

    # Support pur (avec tag Support et pas Fighter/Mage offensif)
    if is_support and not is_fighter and not is_assassin:
        cost[SUPPORT] = 8.0
        cost[TOP]     = 70.0
        cost[JUNGLE]  = 75.0
        cost[MID]     = 55.0 if is_mage else 70.0
        cost[ADC]     = 80.0

    # Mage classique → Mid
    if is_mage and not is_support:
        cost[MID]     = 15.0
        cost[TOP]     = 45.0
        cost[SUPPORT] = 55.0
        cost[ADC]     = 70.0
        cost[JUNGLE]  = 65.0

    # Assassin → Mid > Jungle
    if is_assassin and not is_fighter:
        cost[MID]     = 18.0
        cost[JUNGLE]  = 25.0
        cost[TOP]     = 45.0
        cost[ADC]     = 75.0
        cost[SUPPORT] = 80.0

    # Fighter pur → Top, fallback Jungle
    if is_fighter and not is_assassin and not is_marksman:
        cost[TOP]     = 18.0
        cost[JUNGLE]  = 30.0
        cost[MID]     = 45.0
        cost[SUPPORT] = 65.0
        cost[ADC]     = 75.0

    # Fighter+Assassin (bruisers / divers) → Jungle / Top
    if is_fighter and is_assassin:
        cost[JUNGLE]  = 22.0
        cost[TOP]     = 25.0
        cost[MID]     = 40.0
        cost[ADC]     = 70.0
        cost[SUPPORT] = 75.0

    # Tank pur → Top / Support
    if is_tank and not is_fighter:
        cost[TOP]     = 22.0
        cost[SUPPORT] = 25.0
        cost[JUNGLE]  = 35.0
        cost[MID]     = 60.0
        cost[ADC]     = 80.0

    # Hard locks (override total)
    if champ in HARD_ROLE_LOCKS:
        allowed = HARD_ROLE_LOCKS[champ]
        for role in ROLE_ORDER:
            if role not in allowed:
                cost[role] = max(cost[role], 90.0)
            else:
                cost[role] = min(cost[role], 15.0)

    return cost


def _adjust_cost_with_spells(cost: dict[str, float], spells: set[int], champ_tags: list[str]) -> dict[str, float]:
    """
    Ajuste les coûts selon les summoner spells. Le signal le plus fort = Smite.
    """
    is_marksman = "Marksman" in champ_tags
    is_support  = "Support"  in champ_tags
    is_fighter  = "Fighter"  in champ_tags
    is_tank     = "Tank"     in champ_tags

    # ── SMITE = jungler, lock dur ─────────────────────────────
    # On ne met pas INF partout, car certains modes spéciaux permettent Smite ailleurs,
    # mais on rend les autres rôles très chers.
    if SMITE in spells:
        for role in ROLE_ORDER:
            cost[role] = INF if role != JUNGLE else 1.0
        return cost

    # ── HEAL = ADC ou support, presque jamais ailleurs ───────
    if HEAL in spells:
        if is_marksman:
            cost[ADC]     = max(0.0, cost[ADC] - 30.0)
        elif is_support:
            cost[SUPPORT] = max(0.0, cost[SUPPORT] - 30.0)
        else:
            cost[ADC]     -= 15.0
            cost[SUPPORT] -= 10.0
        cost[TOP]    += 25.0
        cost[JUNGLE] += 30.0
        cost[MID]    += 20.0

    # ── EXHAUST = très majoritairement support ───────────────
    if EXHAUST in spells:
        cost[SUPPORT] -= 25.0
        cost[ADC]     -= 5.0
        cost[TOP]     += 15.0
        cost[JUNGLE]  += 25.0
        cost[MID]     += 10.0

    # ── TP = top en grande majorité, sinon mid (rare) ────────
    if TP in spells or TP2 in spells:
        if is_fighter or is_tank:
            cost[TOP] -= 25.0
            cost[JUNGLE] += 20.0
        else:
            cost[TOP] -= 15.0
            cost[MID] -= 5.0
        cost[SUPPORT] += 15.0
        cost[ADC]     += 25.0  # ADC ne prend presque jamais TP

    # ── IGNITE = mid/top/support agressif ────────────────────
    if IGNITE in spells:
        if is_support:
            cost[SUPPORT] -= 10.0
        else:
            cost[MID] -= 8.0
            cost[TOP] -= 6.0

    # ── BARRIER / CLEANSE = mid ou ADC ───────────────────────
    if BARRIER in spells or CLEANSE in spells:
        cost[MID] -= 10.0
        cost[ADC] -= 8.0
        cost[JUNGLE] += 15.0
        cost[SUPPORT] += 10.0

    # ── GHOST = top ou ADC selon champ ───────────────────────
    if GHOST in spells:
        if is_marksman:
            cost[ADC] -= 12.0
        else:
            cost[TOP] -= 10.0

    return cost


def _adjust_cost_with_history(cost: dict[str, float], history_role: str | None) -> dict[str, float]:
    """
    Si l'historique du joueur indique un main role, on baisse le coût pour ce rôle.
    Signal modéré (les joueurs flexent souvent).
    """
    if not history_role or history_role not in ROLE_ORDER:
        return cost
    cost[history_role] -= 8.0
    return cost


def _adjust_cost_with_position(cost: dict[str, float], position_idx: int | None) -> dict[str, float]:
    """
    En soloQ, l'ordre champ-select est ALÉATOIRE (par tour de pick).
    En tournoi/clash, l'ordre est souvent TOP-JGL-MID-BOT-SUP.
    On applique un BIAIS TRÈS LÉGER (0.5 par rôle) — sert de tiebreaker uniquement.
    """
    if position_idx is None or position_idx < 0 or position_idx >= len(ROLE_ORDER):
        return cost
    expected = ROLE_ORDER[position_idx]
    cost[expected] -= 0.5
    return cost


def _hungarian(cost_matrix: list[list[float]]) -> list[int]:
    """
    Algorithme Hongrois (Munkres). Implémentation pure Python pour éviter scipy.
    Retourne pour chaque ligne (joueur) l'indice de colonne (rôle) assigné.

    Complexité : O(n³). Pour n=5 : trivial.
    Ref : https://en.wikipedia.org/wiki/Hungarian_algorithm
    """
    n = len(cost_matrix)
    if n == 0:
        return []
    m = len(cost_matrix[0])
    if n != m:
        raise ValueError(f"Matrice non carrée : {n}x{m}")

    # Copie pour ne pas modifier l'entrée
    c = [row[:] for row in cost_matrix]

    # Step 1 : réduction par ligne
    for i in range(n):
        row_min = min(c[i])
        for j in range(n):
            c[i][j] -= row_min

    # Step 2 : réduction par colonne
    for j in range(n):
        col_min = min(c[i][j] for i in range(n))
        for i in range(n):
            c[i][j] -= col_min

    # Boucle principale : on cherche un assignment complet par les zéros
    def try_assign() -> list[int]:
        """Tente une assignation gloutonne sur les zéros. Retourne [-1]*n si échec."""
        assigned_col = [-1] * n
        assigned_row = [-1] * n

        for i in range(n):
            zeros = [j for j in range(n) if c[i][j] == 0 and assigned_row[j] == -1]
            if len(zeros) == 1:
                assigned_col[i]    = zeros[0]
                assigned_row[zeros[0]] = i

        # Compléter avec backtracking simple sur les lignes restantes
        unassigned = [i for i in range(n) if assigned_col[i] == -1]

        def bt(idx: int) -> bool:
            if idx >= len(unassigned):
                return True
            i = unassigned[idx]
            for j in range(n):
                if c[i][j] == 0 and assigned_row[j] == -1:
                    assigned_col[i]   = j
                    assigned_row[j]   = i
                    if bt(idx + 1):
                        return True
                    assigned_col[i]   = -1
                    assigned_row[j]   = -1
            return False

        if bt(0):
            return assigned_col
        return [-1] * n

    for _ in range(50):  # garde-fou — converge en pratique en quelques itérations
        result = try_assign()
        if all(r != -1 for r in result):
            return result

        # Cover des zéros et trouver le min non couvert
        covered_rows = set()
        covered_cols = set()

        # Marquage des lignes non assignées
        for i in range(n):
            if result[i] == -1:
                covered_rows.add(i)

        changed = True
        while changed:
            changed = False
            # Marquer les colonnes ayant un zéro dans une ligne marquée
            for i in list(covered_rows):
                for j in range(n):
                    if c[i][j] == 0 and j not in covered_cols:
                        covered_cols.add(j)
                        changed = True
            # Marquer les lignes ayant une assignation dans une colonne marquée
            for j in list(covered_cols):
                for i in range(n):
                    if result[i] == j and i not in covered_rows:
                        covered_rows.add(i)
                        changed = True

        # Le cover effectif = lignes NON marquées + colonnes marquées
        effective_rows = set(range(n)) - covered_rows
        effective_cols = covered_cols

        # Min non couvert
        min_uncovered = INF
        for i in range(n):
            if i in effective_rows:
                continue
            for j in range(n):
                if j in effective_cols:
                    continue
                if c[i][j] < min_uncovered:
                    min_uncovered = c[i][j]

        if min_uncovered == INF:
            break

        # Soustraction au non couvert, addition au double couvert
        for i in range(n):
            for j in range(n):
                row_covered = i not in effective_rows
                col_covered = j in effective_cols
                if not row_covered and not col_covered:
                    c[i][j] -= min_uncovered
                elif row_covered and col_covered:
                    c[i][j] += min_uncovered

    # Fallback : assignation gloutonne par coût croissant
    return _greedy_assign(cost_matrix)


def _greedy_assign(cost_matrix: list[list[float]]) -> list[int]:
    """Fallback : assigne ligne par ligne au plus bas coût restant."""
    n = len(cost_matrix)
    result = [-1] * n
    used_cols: set[int] = set()
    pairs = [(cost_matrix[i][j], i, j) for i in range(n) for j in range(n)]
    pairs.sort()
    for _, i, j in pairs:
        if result[i] == -1 and j not in used_cols:
            result[i] = j
            used_cols.add(j)
            if len(used_cols) == n:
                break
    return result


def _adjust_cost_with_pro_role(cost: dict[str, float], pro_role: str | None) -> dict[str, float]:
    """
    Si on connaît le rôle officiel d'un pro, on baisse FORTEMENT le coût
    pour ce rôle. Plus fort que l'historique (-8) mais pas infini, ce qui
    permet à l'algo Hongrois de résoudre les conflits si deux pros de
    la même équipe sont marqués sur le même rôle (substitut, mauvais seed).
    """
    if not pro_role or pro_role not in ROLE_ORDER:
        return cost
    cost[pro_role] -= 50.0
    return cost

def assign_roles(
    team: list[dict],
    champ_tag_map: dict[str, list] = {},
    history_map:   dict[str, str]  = {},
    pro_role_map:  dict[str, str]  = {},   # ← NOUVEAU
) -> list[str]:
    """
    [...docstring inchangé...]
    pro_role_map: { puuid: role_officiel } — biais fort vers le rôle pro
    """
    n = len(team)
    if n == 0:
        return []
    if n != 5:
        logger.warning(f"assign_roles: équipe à {n} joueurs (attendu 5), fallback ROLE_ORDER")
        return ROLE_ORDER[:n]

    cost_matrix: list[list[float]] = []
    debug_rows = []

    for idx, p in enumerate(team):
        champ    = p.get("championName", "")
        tags     = champ_tag_map.get(champ, [])
        spells   = _spell_set(p)
        hist     = history_map.get(p.get("puuid", ""))
        pro_role = pro_role_map.get(p.get("puuid", ""))   # ← NOUVEAU

        cost = _base_cost_from_tags(champ, tags)
        cost = _adjust_cost_with_spells(cost, spells, tags)
        cost = _adjust_cost_with_history(cost, hist)
        cost = _adjust_cost_with_position(cost, idx)
        cost = _adjust_cost_with_pro_role(cost, pro_role)   # ← NOUVEAU

        cost_matrix.append([cost[role] for role in ROLE_ORDER])
        debug_rows.append((champ, tags, spells, hist, pro_role, cost))

    try:
        col_assignment = _hungarian(cost_matrix)
    except Exception as e:
        logger.error(f"assign_roles: Hongrois failed ({e}), fallback greedy")
        col_assignment = _greedy_assign(cost_matrix)

    result = [ROLE_ORDER[col] if 0 <= col < len(ROLE_ORDER) else "FILL" for col in col_assignment]

    logger.info("🎯 assign_roles (Hungarian) — résultat:")
    for (champ, tags, spells, hist, pro_role, cost), role in zip(debug_rows, result):
        cost_str = " ".join(f"{r}:{cost[r]:.0f}" for r in ROLE_ORDER)
        hist_str = f" hist:{hist}" if hist else ""
        pro_str  = f" pro:{pro_role}" if pro_role else ""
        logger.info(f"   {champ:15s} → {role:8s} | spells={sorted(spells)} | {cost_str}{hist_str}{pro_str}")

    return result