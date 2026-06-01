"""
services/coachdiff_bot.py
Bot CoachDiff réaliste : picks tirés des VRAIES compos de l'équipe (co-occurrence),
biais d'ordre de draft (prio pick d'abord, counterpick Top/Mid en fin, botlane groupée),
bans counter/méta. Tout en IDs DDragon → pas de doublon possible.
"""
from __future__ import annotations
import random, logging
from collections import defaultdict
from sqlalchemy.orm import Session

from models.team_draft        import TeamDraft
from models.champion_pro_stats import ChampionProStats
from models.champion_stats     import ChampionStats
from models.champion_matchups  import ChampionMatchup
from services.champion_naming  import to_ddragon_id
from services.coachdiff_state  import current_turn, all_taken, apply_action, LANES

logger = logging.getLogger(__name__)

# max_per_role : largeur du pool | temp : softmax | cooc : exposant co-occurrence
# order_bias : intensité du biais d'ordre | counter_ban_p / meta_ban_top : bans
DIFFICULTY = {
    "LFL": {"max_per_role": 16, "temp": 2.40, "cooc": 0.4, "order_bias": 0.20, "counter_ban_p": 0.10, "meta_ban_top": 30},
    "KC": {"max_per_role": 12, "temp": 1.70, "cooc": 0.6, "order_bias": 0.40, "counter_ban_p": 0.25, "meta_ban_top": 25},
    "G2": {"max_per_role": 8,  "temp": 1.00, "cooc": 1.2, "order_bias": 0.70, "counter_ban_p": 0.55, "meta_ban_top": 16},
    "T1": {"max_per_role": 5,  "temp": 0.55, "cooc": 2.0, "order_bias": 1.00, "counter_ban_p": 0.85, "meta_ban_top": 10},
}
DEFAULT_OPPONENT  = "G2"
COUNTERPICK_ROLES = {"TOP", "MID"}
BOTLANE           = {"ADC", "SUPPORT"}
COUNTER_MIN_GAMES = 30
COUNTER_MIN_WR    = 0.51


def _cfg(opponent):
    code = opponent if opponent in DIFFICULTY else DEFAULT_OPPONENT
    return code, DIFFICULTY[code]

def _weighted_sample(items, temp):
    if not items:
        return None
    exps = [max(w, 1e-9) ** (1.0 / temp) for _, w in items]
    total = sum(exps)
    if total <= 0:
        return random.choice(items)[0]
    r, acc = random.uniform(0, total), 0.0
    for (key, _), e in zip(items, exps):
        acc += e
        if acc >= r:
            return key
    return items[-1][0]

def _estimate_lanes(db, picks):
    """Estime greedy les lanes probablement occupées par des picks (IDs DDragon)."""
    if not picks:
        return set()
    scores = {}
    for champ in picks:
        for r in (db.query(ChampionStats)
                  .filter(ChampionStats.champion == champ, ChampionStats.tier == "MASTER").all()):
            if r.lane in LANES and r.pickrate and r.pickrate > 0:
                scores[(champ, r.lane)] = float(r.pickrate)
    used_c, used_l, filled = set(), set(), set()
    for (champ, lane), _ in sorted(scores.items(), key=lambda kv: -kv[1]):
        if champ in used_c or lane in used_l:
            continue
        used_c.add(champ); used_l.add(lane); filled.add(lane)
        if len(filled) == len(picks):
            break
    return filled

def _player_open_roles(db, state):
    """Rôles que le joueur peut encore remplir (estimation)."""
    user_key = state["user_side"].lower()
    picks = state.get(user_key, {}).get("picks", [])
    return set(LANES) - _estimate_lanes(db, picks)

def _load_comps(db, team_code):
    rows = db.query(TeamDraft).filter(TeamDraft.team_code == team_code).all()
    return [(r.comp, float(r.weight)) for r in rows if isinstance(r.comp, dict)]

def _role_mult(lane, k, order_bias):
    if lane in COUNTERPICK_ROLES:
        base = 0.45 if k <= 1 else (0.80 if k == 2 else 1.25)   # counterpick repoussé
    else:
        base = 1.0
    return 1.0 + (base - 1.0) * order_bias

def _botlane_mult(lane, plan_lanes, order_bias):
    has_adc, has_sup = "ADC" in plan_lanes, "SUPPORT" in plan_lanes
    if lane in BOTLANE and (has_adc ^ has_sup):
        return 1.0 + 0.9 * order_bias                            # complète le duo bot
    return 1.0


# ─── PICK ─────────────────────────────────────────────────────
def _bot_pick(db, state, cfg, team_code):
    taken = all_taken(state)
    plan  = state.setdefault("bot_plan", {})        # {champ_id: lane}
    plan_lanes  = set(plan.values())
    open_roles  = [l for l in LANES if l not in plan_lanes]
    k = len(plan)
    picked_pairs = {(l, c) for c, l in plan.items()}

    scores = defaultdict(float)
    for comp, w in _load_comps(db, team_code):
        overlap = sum(1 for (l, c) in picked_pairs if comp.get(l) == c)
        factor  = (1.0 + overlap) ** cfg["cooc"]
        for lane in open_roles:
            champ = comp.get(lane)
            if champ and champ not in taken:
                scores[(lane, champ)] += w * factor

    if scores:
        by_role = defaultdict(list)
        for (lane, champ), s in scores.items():
            by_role[lane].append((champ, s))
        items = []
        for lane, lst in by_role.items():
            lst.sort(key=lambda x: -x[1])
            m = _role_mult(lane, k, cfg["order_bias"]) * _botlane_mult(lane, plan_lanes, cfg["order_bias"])
            for champ, s in lst[: cfg["max_per_role"]]:
                items.append(((lane, champ), s * m))
        lane, champ = _weighted_sample(items, cfg["temp"])
        plan[champ] = lane
        return champ

    return _meta_pick_fallback(db, state, open_roles, plan)

def _meta_pick_fallback(db, state, open_roles, plan):
    taken = all_taken(state)
    for lane in open_roles:
        rows = (db.query(ChampionProStats).filter(ChampionProStats.lane == lane)
                .order_by(ChampionProStats.pickrate.desc()).limit(40).all())
        for r in rows:
            cid = to_ddragon_id(r.champion)
            if cid not in taken:
                plan[cid] = lane
                return cid
    rows = db.query(ChampionProStats).order_by(ChampionProStats.pickrate.desc()).limit(120).all()
    for r in rows:
        cid = to_ddragon_id(r.champion)
        if cid not in taken:
            if open_roles:
                plan[cid] = open_roles[0]
            return cid
    raise RuntimeError("bot: aucun champion pickable")


# ─── BAN ──────────────────────────────────────────────────────
# ─── BAN ──────────────────────────────────────────────────────
def _bot_ban(db, state, cfg, team_code):
    taken = all_taken(state)
    plan  = state.get("bot_plan", {})
    player_open = _player_open_roles(db, state)        # ← rôles encore libres côté joueur
    if plan and random.random() < cfg["counter_ban_p"]:
        champ = _best_counter_to_own_picks(db, plan, taken, cfg, player_open)
        if champ:
            return champ
    return (_meta_ban(db, taken, cfg, player_open)
            or _best_counter_to_own_picks(db, plan, taken, cfg, player_open))

def _best_counter_to_own_picks(db, plan, taken, cfg, player_open):
    rows_by_lane = {}
    for lane in set(plan.values()):
        if lane not in player_open:                    # le joueur a déjà rempli ce rôle → inutile
            continue
        rows_by_lane[lane] = (db.query(ChampionMatchup)
            .filter(ChampionMatchup.lane == lane, ChampionMatchup.tier == "MASTER",
                    ChampionMatchup.n_games >= COUNTER_MIN_GAMES).all())
    strengths = {}
    for pick_id, lane in plan.items():
        if lane not in rows_by_lane:                    # rôle filtré ci-dessus
            continue
        for r in rows_by_lane[lane]:
            a, b = to_ddragon_id(r.champion_a), to_ddragon_id(r.champion_b)
            if   a == pick_id: opp, wr = b, 1.0 - float(r.winrate_a)
            elif b == pick_id: opp, wr = a, float(r.winrate_a)
            else: continue
            if opp in taken or wr < COUNTER_MIN_WR:
                continue
            s = wr - 0.5
            if opp not in strengths or s > strengths[opp]:
                strengths[opp] = s
    if not strengths:
        return None
    return _weighted_sample(sorted(strengths.items(), key=lambda x: -x[1]), cfg["temp"])

def _meta_ban(db, taken, cfg, player_open):
    rows = db.query(ChampionProStats).order_by(ChampionProStats.presence.desc()).limit(cfg["meta_ban_top"] * 5).all()
    seen = {}   # cid -> (presence, lane principale)
    for r in rows:
        cid, p, lane = to_ddragon_id(r.champion), float(r.presence), r.lane
        if cid not in seen or p > seen[cid][0]:
            seen[cid] = (p, lane)
    ranked = sorted(seen.items(), key=lambda kv: -kv[1][0])
    items = []
    for cid, (p, lane) in ranked:
        if cid in taken:
            continue
        if lane in LANES and lane not in player_open:   # rôle déjà pris côté joueur → skip
            continue
        items.append((cid, p))
        if len(items) >= cfg["meta_ban_top"]:
            break
    if not items:                                       # filet : plutôt bannir que rien
        items = [(cid, p) for cid, (p, _) in ranked if cid not in taken][: cfg["meta_ban_top"]]
    if not items:
        return None
    return _weighted_sample(items, cfg["temp"])

# ─── API publique ─────────────────────────────────────────────
def bot_play_turn(db, state, opponent=None):
    team_code, cfg = _cfg(opponent)
    turn = current_turn(state)
    if turn is None or turn["actor"] != "BOT":
        raise ValueError("Pas le tour du bot")
    champion = _bot_ban(db, state, cfg, team_code) if turn["action"] == "ban" \
        else _bot_pick(db, state, cfg, team_code)
    if not champion:
        raise RuntimeError("Bot n'a aucun candidat possible")
    apply_action(state, champion, expected_actor="BOT")
    return state, champion


def bot_assign_roles(db, picks, plan=None):
    if plan:
        lanes, ok = {}, True
        for champ in picks:
            lane = plan.get(champ)
            if not lane or lane in lanes:
                ok = False; break
            lanes[lane] = champ
        if ok and len(lanes) == 5:
            return lanes
    return _greedy_assign(db, picks)

def _greedy_assign(db, picks):
    if len(picks) != 5:
        raise ValueError(f"_greedy_assign attend 5 picks, reçu {len(picks)}")
    scores = {}
    for champ in picks:
        for lane in LANES:
            pro = db.query(ChampionProStats).filter(
                ChampionProStats.champion == champ, ChampionProStats.lane == lane).first()
            if pro and pro.pickrate > 0:
                scores[(champ, lane)] = float(pro.pickrate) * 100; continue
            solo = db.query(ChampionStats).filter(
                ChampionStats.champion == champ, ChampionStats.lane == lane,
                ChampionStats.tier == "MASTER").first()
            scores[(champ, lane)] = float(solo.pickrate) if solo and solo.pickrate > 0 else 0.0
    used_c, used_l, out = set(), set(), {}
    for (champ, lane), _ in sorted(scores.items(), key=lambda kv: -kv[1]):
        if champ in used_c or lane in used_l:
            continue
        out[lane] = champ; used_c.add(champ); used_l.add(lane)
        if len(out) == 5:
            break
    for lane, champ in zip([l for l in LANES if l not in used_l],
                           [c for c in picks if c not in used_c]):
        out[lane] = champ
    return out