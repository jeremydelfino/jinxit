"""
services/gm_sim.py
Générateur de timeline de match (cosmétique). NE décide PAS du vainqueur :
on lui passe `winner` (issu de la résolution CoachDiff) et il produit une suite
d'événements pondérée par les stats individuelles + d'équipe, rejouable par le front.

Événements: first_blood, kill, tower, herald, drake, baron, ace, nexus.
Chaque kill porte killer/victim/assists (rôle + champion) → animation + KDA de fin.
"""
import random
from typing import Optional

ROLES = ["TOP", "JUNGLE", "MID", "ADC", "SUPPORT"]
LANE_OF = {"TOP": "top", "JUNGLE": "mid", "MID": "mid", "ADC": "bot", "SUPPORT": "bot"}

# Part de kills / d'assists par rôle dans un combat (les carries closent, sup/jgl assistent)
ROLE_KILL  = {"TOP": 1.0, "JUNGLE": 1.1, "MID": 1.25, "ADC": 1.30, "SUPPORT": 0.55}
ROLE_AST   = {"TOP": 0.9, "JUNGLE": 1.2, "MID": 1.0, "ADC": 0.8, "SUPPORT": 1.5}

# Modificateurs de traits (extensible — alignés sur tes traits de carte)
TRAIT_MOD = {
    "VETERAN":   {"troll": -0.20, "clutch": +4},
    "FRANCHISE": {"troll": -0.10, "carry": +0.12},
    "PRODIGY":   {"carry": +0.10, "troll": +0.08},
    "HOTHEAD":   {"troll": +0.30},
    "SHOTCALLER":{"objective": +0.12},
}


# ─── Accès tolérant (dict OU objet ORM GmPlayerCard) ───────
def _g(o, k, d=0):
    v = getattr(o, k, None) if not isinstance(o, dict) else o.get(k)
    return d if v is None else v


# ─── Profils de force par phase (0-100) ───────────────────
def _early(p): return p["laning"] * 0.60 + p["mechanics"] * 0.25 + p["stress"] * 0.15
def _mid(p):   return p["teamfight"] * 0.40 + p["mechanics"] * 0.30 + p["vision"] * 0.15 + p["clutch"] * 0.15
def _late(p):  return p["teamfight"] * 0.35 + p["clutch"] * 0.30 + p["stress"] * 0.20 + p["mechanics"] * 0.15

PHASE_FN = {"laning": _early, "mid": _mid, "late": _late}


def _troll(p):
    """Poids de mort : sang-froid bas, gros ego, mauvaises mécaniques → feed."""
    t = (100 - p["stress"]) * 0.6
    t += max(0, p["ego"] - 3) * 10
    t += max(0, 65 - p["mechanics"]) * 0.5
    t += p["_trait_troll"] * 100
    return max(2.0, t)


def _carry_bonus(p):
    return 1.0 + p["_trait_carry"]


def _norm_player(card, champion):
    traits = _g(card, "traits", []) or []
    tmod = {"troll": 0.0, "carry": 0.0, "objective": 0.0, "clutch": 0}
    for tr in traits:
        for k, v in TRAIT_MOD.get(str(tr).upper(), {}).items():
            tmod[k] = tmod.get(k, 0) + v
    return {
        "role": (_g(card, "role", "MID") or "MID").upper(),
        "champion": champion,
        "name": _g(card, "name", "") or _g(card, "summoner_name", "") or champion,
        "laning": _g(card, "laning", 70), "teamfight": _g(card, "teamfight", 70),
        "vision": _g(card, "vision", 70), "mechanics": _g(card, "mechanics", 70),
        "stress": _g(card, "stress", 70), "clutch": _g(card, "clutch", 70),
        "ego": _g(card, "ego", 3), "ovr": _g(card, "ovr", 70),
        "_trait_troll": tmod["troll"], "_trait_carry": tmod["carry"],
        "_trait_obj": tmod["objective"], "_clutch_mod": tmod["clutch"],
    }


def build_side(cards, role_to_champ: dict):
    """cards: liste de GmPlayerCard (ou dicts). role_to_champ: {'MID':'Ahri', ...}."""
    out = []
    for c in cards:
        role = (_g(c, "role", "MID") or "MID").upper()
        out.append(_norm_player(c, role_to_champ.get(role, "?")))
    return out


def _team_avg(side, phase):
    fn = PHASE_FN[phase]
    return sum(fn(p) for p in side) / max(1, len(side))


def _pick(rng, side, weight_fn):
    ws = [max(0.01, weight_fn(p)) for p in side]
    r = rng.random() * sum(ws)
    acc = 0
    for p, w in zip(side, ws):
        acc += w
        if r <= acc:
            return p
    return side[-1]


# ═══════════════════════════════════════════════════════════
def generate_timeline(blue_cards, red_cards, role_to_champ: dict,
                      winner: str, duration: Optional[int] = None,
                      seed: Optional[int] = None) -> dict:
    """
    winner: 'blue' | 'red' (décidé en amont).
    role_to_champ: {'blue': {...}, 'red': {...}}.
    """
    rng = random.Random(seed)
    blue = build_side(blue_cards, role_to_champ.get("blue", {}))
    red  = build_side(red_cards,  role_to_champ.get("red", {}))
    sides = {"blue": blue, "red": red}
    loser = "red" if winner == "blue" else "blue"

    # Durée : un stomp est plus court qu'un match serré
    ovr_b = sum(p["ovr"] for p in blue) / 5
    ovr_r = sum(p["ovr"] for p in red) / 5
    gap = abs(ovr_b - ovr_r)
    if duration is None:
        duration = int((28 - min(gap, 16) * 0.45) * 60 + rng.randint(-90, 150))
    duration = max(18 * 60, min(38 * 60, duration))

    laning_end = int(duration * 0.30)
    mid_end    = int(duration * 0.62)

    events = []
    kda = {pid(p, s): {"name": p["name"], "role": p["role"], "champ": p["champion"],
                       "k": 0, "d": 0, "a": 0}
           for s in sides for p in sides[s]}
    towers_left = {"blue": 11, "red": 11}
    first_blood = False

    def phase_at(t):
        return "laning" if t < laning_end else ("mid" if t < mid_end else "late")

    def fight_winner(t):
        ph = phase_at(t)
        diff = _team_avg(sides[winner], ph) - _team_avg(sides[loser], ph)
        # le vainqueur du match gagne la majorité des combats, mais pas tous
        p = 0.55 + 0.0032 * diff
        p = max(0.30, min(0.85, p))
        return winner if rng.random() < p else loser

    def resolve_fight(t, n_kills, lane=None):
        nonlocal first_blood
        ph = phase_at(t)
        wside = fight_winner(t)
        lside = "red" if wside == "blue" else "blue"
        fn = PHASE_FN[ph]
        for _ in range(n_kills):
            killer = _pick(rng, sides[wside], lambda p: fn(p) * ROLE_KILL[p["role"]] * _carry_bonus(p))
            victim = _pick(rng, sides[lside], _troll)
            assists = []
            pool = [p for p in sides[wside] if p is not killer]
            for _a in range(rng.randint(0, 2)):
                if not pool:
                    break
                a = _pick(rng, pool, lambda p: ROLE_AST[p["role"]] + 1)
                pool.remove(a)
                assists.append(a["role"])
            kda[pid(killer, wside)]["k"] += 1
            kda[pid(victim, lside)]["d"] += 1
            for ar in assists:
                tgt = next((p for p in sides[wside] if p["role"] == ar), None)
                if tgt:
                    kda[pid(tgt, wside)]["a"] += 1
            ev = {"t": t, "type": "first_blood" if not first_blood else "kill",
                  "side": wside, "lane": lane or LANE_OF[victim["role"]],
                  "killer": {"role": killer["role"], "champ": killer["champion"], "name": killer["name"]},
                  "victim": {"role": victim["role"], "champ": victim["champion"], "name": victim["name"]},
                  "assists": assists}
            first_blood = True
            events.append(ev)
        if n_kills >= 4:
            events.append({"t": t, "type": "ace", "side": wside})
        return wside

    def tower(t, side, lane=None):
        enemy = "red" if side == "blue" else "blue"
        if towers_left[enemy] <= 0:
            return
        towers_left[enemy] -= 1
        events.append({"t": t, "type": "tower", "side": side,
                       "lane": lane or rng.choice(["top", "mid", "bot"])})

    # ── Phase laning : duels lane, weighted early ──────────
    t = rng.randint(70, 130)
    while t < laning_end:
        w = resolve_fight(t, 1)
        if rng.random() < 0.25:
            tower(t + 10, w)
        t += rng.randint(85, 150)

    # ── Herald + premiers drakes ───────────────────────────
    events.append({"t": rng.randint(8 * 60, 13 * 60), "type": "herald",
                   "side": winner if rng.random() < 0.6 else loser})

    # ── Phase mid : skirmishes + objectifs ─────────────────
    next_drake = laning_end + rng.randint(30, 120)
    while t < mid_end:
        n = rng.randint(1, 2)
        w = resolve_fight(t, n)
        if rng.random() < 0.55:
            tower(t + 12, w)
        if t >= next_drake:
            vis_diff = _team_avg(sides[winner], "mid") - _team_avg(sides[loser], "mid")
            dside = winner if rng.random() < (0.58 + 0.003 * vis_diff) else loser
            events.append({"t": t, "type": "drake", "side": dside})
            next_drake = t + rng.randint(5 * 60, 7 * 60)
        t += rng.randint(60, 110)

    # ── Phase late : teamfights, baron, push final ─────────
    baron_done = False
    while t < duration - 40:
        clutch_diff = sum(p["clutch"] for p in sides[winner]) - sum(p["clutch"] for p in sides[loser])
        n = rng.randint(1, 3 if clutch_diff >= 0 else 2)
        w = resolve_fight(t, n)
        if rng.random() < 0.7:
            tower(t + 12, w)
        if not baron_done and t > duration * 0.70 and rng.random() < 0.5:
            bside = winner if rng.random() < 0.72 else loser
            events.append({"t": t, "type": "baron", "side": bside})
            baron_done = True
        if t >= next_drake:
            events.append({"t": t, "type": "drake", "side": winner if rng.random() < 0.6 else loser})
            next_drake = t + rng.randint(5 * 60, 7 * 60)
        t += rng.randint(45, 90)

    # ── Réconciliation : le vainqueur doit mener aux kills ──
    def kills_of(s):
        return sum(e.get("side") == s for e in events if e.get("type") in ("kill", "first_blood"))
    if kills_of(loser) >= kills_of(winner):
        for _ in range(kills_of(loser) - kills_of(winner) + rng.randint(2, 4)):
            resolve_fight(duration - 50, 1)

    # ── Clôture : baron si pas pris + push nexus ───────────
    if not baron_done:
        events.append({"t": duration - 60, "type": "baron", "side": winner})
    for _ in range(3):
        tower(duration - 40, winner)
    events.append({"t": duration, "type": "nexus", "side": winner})

    events.sort(key=lambda e: e["t"])

    return {
        "winner": winner,
        "duration": duration,
        "draft": role_to_champ,
        "events": events,
        "summary": {
            "score": {"blue": kills_of("blue"), "red": kills_of("red")},
            "objectives": {
                "blue": {"towers": 11 - towers_left["red"],
                         "drakes": sum(e["type"] == "drake" and e["side"] == "blue" for e in events),
                         "barons": sum(e["type"] == "baron" and e["side"] == "blue" for e in events)},
                "red":  {"towers": 11 - towers_left["blue"],
                         "drakes": sum(e["type"] == "drake" and e["side"] == "red" for e in events),
                         "barons": sum(e["type"] == "baron" and e["side"] == "red" for e in events)},
            },
            "players": sorted(kda.values(), key=lambda x: (x["k"] + x["a"]) - x["d"], reverse=True),
        },
    }


def pid(p, side):
    return f"{side}:{p['role']}"


def synthetic_side(strength, names=None, name=None, seed=None):
    """5 joueurs synthétiques autour d'une force d'équipe (bot IA sans cartes)."""
    rng = random.Random(seed)
    if names is None and name:
        names = [f"{name[:8]} {r[:3].title()}" for r in ROLES]
    out = []
    for i, role in enumerate(ROLES):
        base = max(45, min(97, strength + rng.uniform(-5, 5)))
        j = lambda spread=8: int(max(35, min(99, base + rng.uniform(-spread, spread))))
        out.append({
            "role": role, "laning": j(), "teamfight": j(), "vision": j(),
            "mechanics": j(), "stress": j(11), "clutch": j(11),
            "ego": rng.randint(2, 4), "ovr": int(base), "traits": [],
            "name": names[i] if names and i < len(names) else role.title(),
        })
    return out

# ─── Démo / test rapide ────────────────────────────────────
if __name__ == "__main__":
    def card(role, l, t, v, m, s, c, ego=3, traits=None, name=None):
        return {"role": role, "laning": l, "teamfight": t, "vision": v, "mechanics": m,
                "stress": s, "clutch": c, "ego": ego, "ovr": (l + t + v + m + s + c) // 6,
                "traits": traits or [], "name": name}

    blue = [
        card("TOP", 82, 80, 70, 84, 78, 75, name="BlueTop"),
        card("JUNGLE", 75, 85, 88, 80, 80, 82, traits=["SHOTCALLER"], name="BlueJgl"),
        card("MID", 88, 86, 75, 92, 84, 88, ego=4, traits=["PRODIGY"], name="BlueMid"),
        card("ADC", 84, 90, 65, 90, 80, 85, name="BlueAdc"),
        card("SUPPORT", 70, 82, 90, 72, 85, 80, traits=["VETERAN"], name="BlueSup"),
    ]
    red = [
        card("TOP", 78, 76, 68, 78, 72, 70, name="RedTop"),
        card("JUNGLE", 72, 74, 80, 75, 70, 72, name="RedJgl"),
        card("MID", 80, 78, 70, 82, 60, 74, ego=5, traits=["HOTHEAD"], name="RedMid"),  # le troll
        card("ADC", 82, 80, 64, 84, 75, 78, name="RedAdc"),
        card("SUPPORT", 68, 76, 84, 70, 78, 74, name="RedSup"),
    ]
    champs = {"blue": {"TOP": "Aatrox", "JUNGLE": "LeeSin", "MID": "Ahri", "ADC": "Jinx", "SUPPORT": "Thresh"},
              "red":  {"TOP": "Ornn", "JUNGLE": "Viego", "MID": "Azir", "ADC": "Kaisa", "SUPPORT": "Nautilus"}}

    tl = generate_timeline(blue, red, champs, winner="blue", seed=42)
    print(f"Vainqueur: {tl['winner']} · durée {tl['duration']//60}:{tl['duration']%60:02d} · "
          f"score {tl['summary']['score']}")
    print("--- KDA ---")
    for p in tl["summary"]["players"]:
        print(f"  {p['name']:8} {p['role']:8} {p['champ']:9} {p['k']}/{p['d']}/{p['a']}")
    print(f"--- {len(tl['events'])} events ---")
    for e in tl["events"][:12]:
        print(" ", e)