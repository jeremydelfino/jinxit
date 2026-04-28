"""
services/live_odds_engine.py
Moteur de côtes pour les games live (ranked solo/duo).

Score d'équipe (somme des poids = 1.0) :
  player_strength    0.40   joueurs : winrate global, winrate sur le champ joué, forme 5 dernières
  champion_strength  0.35   ChampionStats : winrate du champion sur sa lane (DB)
  synergy_strength   0.20   ChampionSynergy : somme des synergy_score des paires de la compo (DB)
  meta_strength      0.05   ChampionStats : pickrate moyen (compo méta vs off-meta)

Polarisation finale par exponentiation : prob = score^EXPONENT / sum.
"""
import asyncio
import logging
import time
from database import SessionLocal
from models.champion_stats import ChampionStats
from models.champion_synergy import ChampionSynergy
from services.riot_stats import get_player_stats

logger = logging.getLogger(__name__)

# ─── Paramètres bookmaker ────────────────────────────────────
MARGIN     = 0.92
EXPONENT   = 4.5
MIN_ODDS   = 1.05
MAX_ODDS   = 15.0
PROB_FLOOR = 0.04
PROB_CEIL  = 0.96
SPREAD_GAIN = 1.5    # amplification (score - 0.5) avant polarisation

# ─── Poids du score d'équipe ─────────────────────────────────
WEIGHTS = {
    "player":   0.40,
    "champion": 0.35,
    "synergy":  0.20,
    "meta":     0.05,
}
PLAYER_SUB = {
    "winrate_global": 0.40,
    "winrate_champ":  0.35,
    "forme_5":        0.25,
}

# ─── Côtes fixes des paris non-victoire ──────────────────────
FIXED_ODDS = {
    "first_blood":            8.0,
    "first_tower":            2.5,
    "first_dragon":           2.5,
    "first_baron":            3.0,
    "game_duration_under25":  2.8,
    "game_duration_25_35":    1.8,
    "game_duration_over35":   2.5,
    "player_positive_kda":    2.2,
    "champion_kda_over25":    2.5,
    "champion_kda_over5":     3.5,
    "champion_kda_over10":    6.0,
    "top_damage":             3.0,
    "jungle_gap":             2.0,
}

ROLE_TO_LANE = {
    "TOP": "TOP", "JUNGLE": "JUNGLE", "MID": "MID", "MIDDLE": "MID",
    "ADC": "ADC", "BOTTOM": "ADC", "SUPPORT": "SUPPORT", "UTILITY": "SUPPORT",
}


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


# ──────────────────────────────────────────────────────────────
# CACHE DB (10 min) — évite de hammer ChampionStats à chaque game
# ──────────────────────────────────────────────────────────────

_DB_CACHE: dict = {}
_DB_TTL_SECONDS = 600


def _cache_get(key: str):
    entry = _DB_CACHE.get(key)
    if not entry or time.time() > entry["expires_at"]:
        _DB_CACHE.pop(key, None)
        return None
    return entry["data"]


def _cache_set(key: str, data):
    _DB_CACHE[key] = {"data": data, "expires_at": time.time() + _DB_TTL_SECONDS}


def _load_champion_stats() -> dict | None:
    """
    { (champion, lane): {winrate, pickrate, n_games} }
    Agrège EUW + KR par moyenne pondérée sur n_games. Tier MASTER.
    Retourne None si DB vide.
    """
    cached = _cache_get("champ_stats")
    if cached is not None:
        return cached

    db = SessionLocal()
    try:
        rows = db.query(ChampionStats).filter(ChampionStats.tier == "MASTER").all()
        if not rows:
            logger.warning("⚠️  ChampionStats DB vide — fallback hardcodé activé")
            return None

        agg: dict = {}
        for r in rows:
            key = (r.champion, r.lane)
            if key not in agg:
                agg[key] = {"wins": 0, "total": 0}
            agg[key]["wins"]  += r.wins
            agg[key]["total"] += r.n_games

        total_by_lane: dict = {}
        for (_, lane), d in agg.items():
            total_by_lane[lane] = total_by_lane.get(lane, 0) + d["total"]

        result = {}
        for (champ, lane), d in agg.items():
            if d["total"] < 20:
                continue
            wr = d["wins"] / d["total"]
            pr = d["total"] / max(total_by_lane.get(lane, 1), 1)
            result[(champ, lane)] = {"winrate": wr, "pickrate": pr, "n_games": d["total"]}

        _cache_set("champ_stats", result)
        logger.info(f"📥 ChampionStats DB → {len(result)} (champion, lane) chargés")
        return result
    except Exception as e:
        logger.warning(f"_load_champion_stats failed: {e}")
        return None
    finally:
        db.close()


def _load_synergies() -> dict | None:
    """{ frozenset({champA, champB}): synergy_score } depuis DB."""
    cached = _cache_get("synergies")
    if cached is not None:
        return cached

    db = SessionLocal()
    try:
        rows = db.query(ChampionSynergy).filter(
            ChampionSynergy.tier == "MASTER",
            ChampionSynergy.synergy_score > 0.02,
        ).all()
        if not rows:
            logger.warning("⚠️  ChampionSynergy DB vide — pas de bonus synergie")
            return None
        result = {frozenset({r.champion_a, r.champion_b}): r.synergy_score for r in rows}
        _cache_set("synergies", result)
        logger.info(f"📥 ChampionSynergy DB → {len(result)} paires chargées")
        return result
    except Exception as e:
        logger.warning(f"_load_synergies failed: {e}")
        return None
    finally:
        db.close()


# ──────────────────────────────────────────────────────────────
# COMPOSANTES DU SCORE
# ──────────────────────────────────────────────────────────────

def _player_strength(stats: dict) -> float:
    return (
        stats["winrate_global"] * PLAYER_SUB["winrate_global"]
        + stats["winrate_champ"]  * PLAYER_SUB["winrate_champ"]
        + stats["forme_5"]        * PLAYER_SUB["forme_5"]
    )


def _champion_strength(team: list[dict], champ_stats: dict | None) -> tuple[float, dict]:
    """Moyenne des winrates des 5 champions sur leur lane."""
    wrs = []
    detail = {}
    for p in team:
        champ = p.get("championName") or ""
        role  = (p.get("role") or "").upper()
        lane  = ROLE_TO_LANE.get(role, "")

        wr = 0.50
        if champ_stats and lane:
            entry = champ_stats.get((champ, lane))
            if entry:
                wr = entry["winrate"]
            else:
                # Fallback : moyenne pondérée toutes lanes pour ce champ
                all_lanes = [v for (c, _), v in champ_stats.items() if c == champ]
                if all_lanes:
                    tot = sum(v["n_games"] for v in all_lanes)
                    wr = sum(v["winrate"] * v["n_games"] for v in all_lanes) / tot

        wrs.append(wr)
        detail[champ or "?"] = round(wr, 3)

    return (sum(wrs) / len(wrs) if wrs else 0.50), detail


def _synergy_strength(team: list[dict], synergies: dict | None) -> tuple[float, list]:
    """Score [0.20, 0.90] basé sur la somme des synergy_score des paires de la compo."""
    if not synergies:
        return 0.50, []

    champs = [p.get("championName", "") for p in team if p.get("championName")]
    bonus = 0.0
    pairs_found = []
    seen = set()
    for i in range(len(champs)):
        for j in range(i + 1, len(champs)):
            pair = frozenset({champs[i], champs[j]})
            if pair in synergies and pair not in seen:
                bonus += synergies[pair]
                seen.add(pair)
                pairs_found.append({"champs": list(pair), "score": round(synergies[pair], 3)})

    # synergy_score typique ∈ [0.02, 0.10] par paire. Compo synergique max ≈ 0.30.
    # Mapping linéaire : 0 → 0.50, 0.30 → 0.90.
    score = 0.50 + min(bonus, 0.30) * (0.40 / 0.30)
    return _clamp(score, 0.20, 0.90), pairs_found


def _meta_strength(team: list[dict], champ_stats: dict | None) -> float:
    """Pickrate moyen → compo méta = score haut, off-meta = score bas."""
    if not champ_stats:
        return 0.50
    prs = []
    for p in team:
        champ = p.get("championName") or ""
        lane  = ROLE_TO_LANE.get((p.get("role") or "").upper(), "")
        if not lane:
            continue
        entry = champ_stats.get((champ, lane))
        if entry:
            prs.append(entry["pickrate"])

    if not prs:
        return 0.50

    avg = sum(prs) / len(prs)
    # pickrate typique ∈ [0.02, 0.12]. Mapping linéaire → [0.20, 0.80].
    return _clamp(0.20 + (avg - 0.02) / 0.10 * 0.60, 0.20, 0.90)


# ──────────────────────────────────────────────────────────────
# SCORE D'ÉQUIPE
# ──────────────────────────────────────────────────────────────

async def _team_score(team: list[dict], region: str) -> tuple[float, dict]:
    # Stats joueurs (Riot API en parallèle)
    tasks = []
    for p in team:
        if p.get("puuid"):
            tasks.append(get_player_stats(p["puuid"], region, p.get("championName")))
        else:
            tasks.append(_default_stats_coro())

    stats_list = await asyncio.gather(*tasks, return_exceptions=True)
    valid_stats, players_detail = [], []
    for p, stats in zip(team, stats_list):
        if isinstance(stats, Exception) or stats is None:
            stats = _default_stats_dict()
        valid_stats.append(stats)
        players_detail.append({
            "summonerName":   p.get("summonerName", ""),
            "championName":   p.get("championName", ""),
            "role":           p.get("role", ""),
            "winrate_global": stats["winrate_global"],
            "winrate_champ":  stats["winrate_champ"],
            "forme_5":        stats["forme_5"],
            "n_games":        stats["n_games"],
        })

    avg_player = (
        sum(_player_strength(s) for s in valid_stats) / len(valid_stats)
        if valid_stats else 0.50
    )

    # DB-backed
    champ_stats = _load_champion_stats()
    synergies   = _load_synergies()

    champ_score, champ_detail   = _champion_strength(team, champ_stats)
    syn_score,   syn_pairs      = _synergy_strength(team, synergies)
    meta_score                  = _meta_strength(team, champ_stats)

    score = (
        avg_player    * WEIGHTS["player"]
        + champ_score  * WEIGHTS["champion"]
        + syn_score    * WEIGHTS["synergy"]
        + meta_score   * WEIGHTS["meta"]
    )
    # Amplification de l'écart au centre puis clamp
    score = 0.50 + (score - 0.50) * SPREAD_GAIN
    score = _clamp(score, 0.10, 0.90)

    detail = {
        "score_total":       round(score, 3),
        "player_strength":   round(avg_player, 3),
        "champion_strength": round(champ_score, 3),
        "synergy_strength":  round(syn_score, 3),
        "meta_strength":     round(meta_score, 3),
        "synergy_pairs":     syn_pairs,
        "champ_winrates":    champ_detail,
        "players":           players_detail,
        "db_loaded": {
            "champion_stats": champ_stats is not None,
            "synergies":      synergies is not None,
        },
    }
    return score, detail


async def _default_stats_coro() -> dict:
    return _default_stats_dict()


def _default_stats_dict() -> dict:
    return {"winrate_global": 0.50, "winrate_champ": 0.50, "forme_5": 0.50, "n_games": 0, "n_games_champ": 0}


# ──────────────────────────────────────────────────────────────
# JUNGLE GAP — nouvelle formule basée sur DB
# ──────────────────────────────────────────────────────────────

async def compute_jungle_gap_odds(
    blue_team: list[dict],
    red_team:  list[dict],
    region:    str = "EUW",
) -> dict:
    """
    Score jungler =
        0.30  winrate_global du joueur
      + 0.25  winrate_champ du joueur (sur le champ joué)
      + 0.15  forme_5
      + 0.20  winrate du champion en JUNGLE (ChampionStats DB)
      + 0.10  synergie JG ↔ MID de la même équipe (ChampionSynergy DB)

    La synergie JG-MID est un signal très fort en LoL (gank coordonnés,
    early roams type Lee Sin + Sylas, Nidalee + Akali...).
    """
    def find_role(team: list[dict], target: str) -> dict | None:
        for p in team:
            if (p.get("role") or "").upper() == target:
                return p
        if target == "JUNGLE":
            for p in team:
                if 11 in {p.get("spell1Id"), p.get("spell2Id")}:
                    return p
        return None

    jg_blue,  jg_red  = find_role(blue_team, "JUNGLE"), find_role(red_team, "JUNGLE")
    mid_blue, mid_red = find_role(blue_team, "MID"),    find_role(red_team, "MID")

    champ_stats = _load_champion_stats()
    synergies   = _load_synergies()

    async def jg_score(jg: dict | None, mid: dict | None) -> tuple[float, dict]:
        if not jg or not jg.get("puuid"):
            return 0.50, {"reason": "no_jungler_found"}

        try:
            stats = await asyncio.wait_for(
                get_player_stats(jg["puuid"], region, jg.get("championName")),
                timeout=8.0,
            )
        except Exception:
            stats = _default_stats_dict()

        player_part = (
            stats["winrate_global"] * 0.30
            + stats["winrate_champ"] * 0.25
            + stats["forme_5"]       * 0.15
        )

        # Winrate du champion en JUNGLE
        jg_champ = jg.get("championName") or ""
        champ_wr = 0.50
        if champ_stats:
            entry = champ_stats.get((jg_champ, "JUNGLE"))
            if entry:
                champ_wr = entry["winrate"]

        # Synergie JG ↔ MID (signal fort)
        synergy_norm = 0.50
        synergy_raw  = 0.0
        if mid and mid.get("championName") and synergies:
            pair = frozenset({jg_champ, mid["championName"]})
            synergy_raw = synergies.get(pair, 0.0)
            # synergy_score ∈ [0.02, 0.10] généralement → mapping vers [0.50, 0.80]
            synergy_norm = _clamp(0.50 + synergy_raw * 3.0, 0.30, 0.80)

        score = player_part + champ_wr * 0.20 + synergy_norm * 0.10

        return score, {
            "jungler":         f"{jg.get('summonerName','?')} ({jg_champ})",
            "mid_laner":       f"{mid.get('summonerName','?')} ({mid.get('championName','?')})" if mid else None,
            "winrate_global":  round(stats["winrate_global"], 3),
            "winrate_champ":   round(stats["winrate_champ"], 3),
            "forme_5":         round(stats["forme_5"], 3),
            "champ_wr_jungle": round(champ_wr, 3),
            "synergy_jg_mid":  round(synergy_raw, 3),
            "score_total":     round(score, 3),
        }

    (sb, db_), (sr, dr_) = await asyncio.gather(
        jg_score(jg_blue, mid_blue),
        jg_score(jg_red,  mid_red),
    )

    # Polarisation forte sur le jungle gap
    s_blue = max(sb, 0.01) ** 3.5
    s_red  = max(sr, 0.01) ** 3.5
    total  = s_blue + s_red
    prob_blue = _clamp(s_blue / total, 0.10, 0.90) if total > 0 else 0.50
    prob_red  = 1.0 - prob_blue

    odds_blue = round(_clamp((1.0 / prob_blue) * 0.90, 1.15, 8.00), 2)
    odds_red  = round(_clamp((1.0 / prob_red)  * 0.90, 1.15, 8.00), 2)

    logger.info(
        f"🌿 jungle_gap → blue={sb:.3f} ({db_.get('jungler')}) vs "
        f"red={sr:.3f} ({dr_.get('jungler')}) → odds {odds_blue}/{odds_red}"
    )

    return {
        "blue":        odds_blue,
        "red":         odds_red,
        "detail_blue": db_,
        "detail_red":  dr_,
    }


# ──────────────────────────────────────────────────────────────
# COMPUTE LIVE ODDS — POINT D'ENTRÉE
# ──────────────────────────────────────────────────────────────

async def compute_live_odds(
    blue_team: list[dict],
    red_team:  list[dict],
    region:    str = "EUW",
) -> dict:
    (score_blue, detail_blue), (score_red, detail_red) = await asyncio.gather(
        _team_score(blue_team, region),
        _team_score(red_team,  region),
    )

    s_blue = max(score_blue, 0.01) ** EXPONENT
    s_red  = max(score_red,  0.01) ** EXPONENT
    total  = s_blue + s_red

    prob_blue = _clamp(s_blue / total, PROB_FLOOR, PROB_CEIL) if total > 0 else 0.50
    prob_red  = 1.0 - prob_blue

    odds_blue = round(_clamp((1.0 / prob_blue) * MARGIN, MIN_ODDS, MAX_ODDS), 2)
    odds_red  = round(_clamp((1.0 / prob_red)  * MARGIN, MIN_ODDS, MAX_ODDS), 2)

    favor_blue = prob_blue - 0.50

    def obj_odds(base: float, favor: float, side: str) -> float:
        adj = -favor if side == "blue" else favor
        return round(_clamp(base * (1 + adj * 0.50), 1.15, base * 2.0), 2)

    try:
        jg_odds = await asyncio.wait_for(
            compute_jungle_gap_odds(blue_team, red_team, region),
            timeout=10.0,
        )
    except Exception as e:
        logger.warning(f"jungle_gap failed ({e}), fallback fixed")
        jg_odds = {"blue": 2.0, "red": 2.0, "detail_blue": {}, "detail_red": {}}

    logger.info(
        f"📊 compute_live_odds → score_blue={score_blue:.3f} score_red={score_red:.3f} "
        f"| ^{EXPONENT} → prob_blue={prob_blue:.3f} | odds {odds_blue}/{odds_red}"
    )

    return {
        "who_wins":              {"blue": odds_blue, "red": odds_red},
        "first_blood":           {"odds": FIXED_ODDS["first_blood"]},
        "first_tower":           {"blue": obj_odds(FIXED_ODDS["first_tower"],  favor_blue, "blue"),
                                  "red":  obj_odds(FIXED_ODDS["first_tower"],  favor_blue, "red")},
        "first_dragon":          {"blue": obj_odds(FIXED_ODDS["first_dragon"], favor_blue, "blue"),
                                  "red":  obj_odds(FIXED_ODDS["first_dragon"], favor_blue, "red")},
        "first_baron":           {"blue": obj_odds(FIXED_ODDS["first_baron"],  favor_blue, "blue"),
                                  "red":  obj_odds(FIXED_ODDS["first_baron"],  favor_blue, "red")},
        "game_duration_under25": {"odds": FIXED_ODDS["game_duration_under25"]},
        "game_duration_25_35":   {"odds": FIXED_ODDS["game_duration_25_35"]},
        "game_duration_over35":  {"odds": FIXED_ODDS["game_duration_over35"]},
        "player_positive_kda":   {"odds": FIXED_ODDS["player_positive_kda"]},
        "champion_kda_over25":   {"odds": FIXED_ODDS["champion_kda_over25"]},
        "champion_kda_over5":    {"odds": FIXED_ODDS["champion_kda_over5"]},
        "champion_kda_over10":   {"odds": FIXED_ODDS["champion_kda_over10"]},
        "top_damage":            {"odds": FIXED_ODDS["top_damage"]},
        "jungle_gap":            {"blue": jg_odds["blue"], "red": jg_odds["red"]},

        "score_blue":  round(score_blue, 3),
        "score_red":   round(score_red,  3),
        "prob_blue":   round(prob_blue, 3),
        "prob_red":    round(prob_red,  3),
        "detail_blue": detail_blue,
        "detail_red":  detail_red,
        "jungle_gap_detail": {
            "blue": jg_odds.get("detail_blue", {}),
            "red":  jg_odds.get("detail_red",  {}),
        },
    }