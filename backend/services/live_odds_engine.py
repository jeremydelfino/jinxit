"""
services/live_odds_engine.py
Moteur de côtes pour les games live (ranked solo/duo avec pros ou joueurs lambda).

Formule par équipe :
  score = winrate_global * 0.25
        + winrate_champ  * 0.25
        + forme_5        * 0.20
        + winrate_team   * 0.10   (moyenne winrate_global des 5 joueurs)
        + draft_score    * 0.20

  prob_blue = score_blue / (score_blue + score_red)
  cote_blue = (1 / prob_blue) * MARGIN
  cote_red  = (1 / prob_red)  * MARGIN
"""
import asyncio
import logging
from services.riot_stats import get_player_stats

logger = logging.getLogger(__name__)

# ─── Paramètres bookmaker ────────────────────────────────────
MARGIN    = 0.92   # Marge bookmaker (~8%)
MIN_ODDS  = 1.20
MAX_ODDS  = 4.00

# ─── Poids du score d'équipe ─────────────────────────────────
WEIGHTS = {
    "winrate_global": 0.25,
    "winrate_champ":  0.25,
    "forme_5":        0.20,
    "winrate_team":   0.10,
    "draft":          0.20,
}

# ─── Côtes fixes pour les paris non-victoire ─────────────────
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
    "jungle_gap":             2.0,   # placeholder — remplacé par dynamique
}

# ─── Tier list champions (winrate moyen patch actuel) ────────
# Source : approximations u.gg patch 15.x — à mettre à jour chaque gros patch
CHAMP_WINRATE: dict[str, float] = {
    # TOP
    "Darius": 0.52, "Garen": 0.53, "Malphite": 0.52, "Sett": 0.51,
    "Fiora": 0.50, "Camille": 0.49, "Irelia": 0.48, "Riven": 0.49,
    "Jax": 0.51, "Nasus": 0.54, "Teemo": 0.52, "Urgot": 0.52,
    "Aatrox": 0.50, "Gnar": 0.50, "Renekton": 0.49, "Ornn": 0.51,
    "Grasp": 0.50, "Vladimir": 0.50, "Kennen": 0.50, "Gangplank": 0.49,
    # JUNGLE
    "LeeSin": 0.47, "Vi": 0.52, "Warwick": 0.54, "Hecarim": 0.52,
    "Nocturne": 0.53, "Amumu": 0.54, "Zac": 0.53, "Jarvan IV": 0.51,
    "Nidalee": 0.47, "Elise": 0.48, "Graves": 0.50, "Kindred": 0.49,
    "Kha'Zix": 0.51, "Rengar": 0.50, "Shaco": 0.51, "Udyr": 0.52,
    "Viego": 0.50, "Lillia": 0.51, "Diana": 0.52, "Evelynn": 0.50,
    # MID
    "Zed": 0.50, "Syndra": 0.51, "Orianna": 0.51, "Viktor": 0.50,
    "Lux": 0.53, "Veigar": 0.53, "Annie": 0.54, "Malzahar": 0.53,
    "Ahri": 0.52, "Yasuo": 0.49, "Yone": 0.50, "Katarina": 0.50,
    "Akali": 0.48, "Fizz": 0.51, "Cassiopeia": 0.51, "Twisted Fate": 0.50,
    # ADC
    "Jinx": 0.53, "Caitlyn": 0.51, "Miss Fortune": 0.53, "Ashe": 0.53,
    "Jhin": 0.52, "Sivir": 0.52, "Xayah": 0.51, "Draven": 0.50,
    "Kai'Sa": 0.51, "Ezreal": 0.49, "Lucian": 0.49, "Tristana": 0.51,
    "Twitch": 0.52, "Kog'Maw": 0.53, "Samira": 0.51, "Zeri": 0.50,
    # SUPPORT
    "Thresh": 0.50, "Lulu": 0.53, "Nautilus": 0.52, "Blitzcrank": 0.52,
    "Soraka": 0.54, "Nami": 0.53, "Janna": 0.54, "Morgana": 0.52,
    "Leona": 0.51, "Alistar": 0.51, "Braum": 0.51, "Pyke": 0.50,
    "Senna": 0.51, "Zyra": 0.52, "Bard": 0.50, "Karma": 0.52,
}

# ─── Synergies connues (paires de champions) ─────────────────
# Score bonus [0, 1] ajouté au draft_score si la paire est présente dans la même équipe
SYNERGIES: dict[frozenset, float] = {
    # Engage + Follow-up
    frozenset({"Amumu",      "Miss Fortune"}): 0.15,
    frozenset({"Orianna",    "Yasuo"}):        0.15,
    frozenset({"Orianna",    "Yone"}):         0.12,
    frozenset({"Malphite",   "Miss Fortune"}): 0.14,
    frozenset({"Malphite",   "Jinx"}):         0.12,
    frozenset({"Engage",     "Zed"}):          0.08,
    frozenset({"Leona",      "Draven"}):       0.13,
    frozenset({"Leona",      "Lucian"}):       0.11,
    frozenset({"Nautilus",   "Jinx"}):         0.11,
    frozenset({"Nautilus",   "Caitlyn"}):      0.10,
    frozenset({"Blitzcrank", "Caitlyn"}):      0.12,
    frozenset({"Thresh",     "Lucian"}):       0.13,
    frozenset({"Thresh",     "Jinx"}):         0.10,
    frozenset({"Lulu",       "Kai'Sa"}):       0.14,
    frozenset({"Lulu",       "Xayah"}):        0.12,
    frozenset({"Lulu",       "Jinx"}):         0.11,
    # Poke + Poke
    frozenset({"Caitlyn",    "Zyra"}):         0.11,
    frozenset({"Jayce",      "Ezreal"}):       0.10,
    frozenset({"Jayce",      "Karma"}):        0.09,
    # Dive / assassin
    frozenset({"Zac",        "Zed"}):          0.10,
    frozenset({"Jarvan IV",  "Zed"}):          0.11,
    frozenset({"Jarvan IV",  "Katarina"}):     0.12,
    frozenset({"Hecarim",    "Yone"}):         0.10,
    # Protect-the-carry
    frozenset({"Lulu",       "Tristana"}):     0.13,
    frozenset({"Janna",      "Kai'Sa"}):       0.12,
    frozenset({"Karma",      "Xayah"}):        0.11,
    frozenset({"Soraka",     "Kog'Maw"}):      0.13,
    frozenset({"Nami",       "Ezreal"}):       0.12,
    # Tank + Peel
    frozenset({"Malphite",   "Syndra"}):       0.09,
    frozenset({"Ornn",       "Jinx"}):         0.10,
    frozenset({"Ornn",       "Aphelios"}):     0.11,
    # Special
    frozenset({"Twisted Fate", "Nocturne"}):   0.13,
    frozenset({"Twisted Fate", "Zed"}):        0.11,
    frozenset({"Shen",       "Miss Fortune"}): 0.12,
    frozenset({"Shen",       "Jinx"}):         0.11,
}


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def _draft_score(champ_names: list[str]) -> float:
    """
    Score de draft [0, 1] basé sur :
    - Moyenne des winrates champion (tier list)
    - Bonus synergies détectées dans la composition
    """
    champs = [c for c in champ_names if c]

    # Winrate moyen des champions
    wr_list  = [CHAMP_WINRATE.get(c, 0.50) for c in champs]
    wr_mean  = sum(wr_list) / len(wr_list) if wr_list else 0.50

    # Bonus synergies (on cherche toutes les paires)
    synergie_bonus = 0.0
    seen = set()
    for i in range(len(champs)):
        for j in range(i + 1, len(champs)):
            pair = frozenset({champs[i], champs[j]})
            if pair in SYNERGIES and pair not in seen:
                synergie_bonus += SYNERGIES[pair]
                seen.add(pair)

    # Le bonus synergies est cappé à 0.15 pour ne pas exploser
    synergie_bonus = min(synergie_bonus, 0.15)

    # Score final : combinaison winrate champion + synergies
    # On normalise : winrate est déjà [0.45, 0.55] environ, on centre sur 0.5
    draft = (wr_mean - 0.50) * 2 + 0.50   # ramène vers [-0.10, +0.10] autour de 0.5
    draft = _clamp(draft + synergie_bonus, 0.30, 0.85)

    return round(draft, 3)


async def _team_score(team: list[dict], region: str) -> tuple[float, list[dict]]:
    """
    Calcule le score [0, 1] d'une équipe.
    Retourne (score, details_par_joueur).
    """
    tasks = []
    for p in team:
        puuid = p.get("puuid")
        champ = p.get("championName")
        if puuid:
            tasks.append(get_player_stats(puuid, region, champ))
        else:
            tasks.append(asyncio.coroutine(lambda: None)()) if False else None
            # Joueur sans puuid → stats par défaut
            tasks.append(_default_stats_coro())

    stats_list = await asyncio.gather(*tasks, return_exceptions=True)

    player_details = []
    valid_stats    = []

    for p, stats in zip(team, stats_list):
        if isinstance(stats, Exception) or stats is None:
            stats = _default_stats_dict()
        valid_stats.append(stats)
        player_details.append({
            "summonerName":   p.get("summonerName", ""),
            "championName":   p.get("championName", ""),
            "winrate_global": stats["winrate_global"],
            "winrate_champ":  stats["winrate_champ"],
            "forme_5":        stats["forme_5"],
            "n_games":        stats["n_games"],
        })

    # Winrate moyen de l'équipe (signal cohésion)
    wr_team_mean = sum(s["winrate_global"] for s in valid_stats) / len(valid_stats) if valid_stats else 0.50

    # Score individuel moyen
    def player_score(s: dict) -> float:
        return (
            s["winrate_global"] * WEIGHTS["winrate_global"] / (WEIGHTS["winrate_global"] + WEIGHTS["winrate_champ"] + WEIGHTS["forme_5"])
            + s["winrate_champ"] * WEIGHTS["winrate_champ"] / (WEIGHTS["winrate_global"] + WEIGHTS["winrate_champ"] + WEIGHTS["forme_5"])
            + s["forme_5"]       * WEIGHTS["forme_5"]       / (WEIGHTS["winrate_global"] + WEIGHTS["winrate_champ"] + WEIGHTS["forme_5"])
        )

    avg_player_score = sum(player_score(s) for s in valid_stats) / len(valid_stats) if valid_stats else 0.50

    # Draft score
    champ_names  = [p.get("championName") for p in team]
    draft        = _draft_score(champ_names)

    # Score final pondéré
    score = (
        avg_player_score   * (WEIGHTS["winrate_global"] + WEIGHTS["winrate_champ"] + WEIGHTS["forme_5"])
        + wr_team_mean     * WEIGHTS["winrate_team"]
        + draft            * WEIGHTS["draft"]
    )

    return _clamp(score, 0.20, 0.80), player_details


async def _default_stats_coro() -> dict:
    return _default_stats_dict()


def _default_stats_dict() -> dict:
    return {"winrate_global": 0.50, "winrate_champ": 0.50, "forme_5": 0.50, "n_games": 0, "n_games_champ": 0}

async def compute_jungle_gap_odds(
    blue_team: list[dict],
    red_team:  list[dict],
    region:    str = "EUW",
) -> dict:
    """
    Côtes Jungle Gap basées sur les stats historiques réelles des junglers.
    Détecte les junglers via :
      1. role == "JUNGLE" (stocké en DB depuis Spectator V5 — source principale)
      2. Smite (spell 11) — fallback si role absent
      3. Index 1 dans l'équipe — dernier recours
    """
    from services.riot_stats import get_player_stats

    def find_jungler(team: list[dict]) -> dict | None:
        # Priorité 1 : rôle stocké en DB (détecté via Smite ou ProPlayer en live)
        for p in team:
            if (p.get("role") or "").upper() == "JUNGLE":
                return p
        # Priorité 2 : Smite dans les spells (cas où role n'est pas encore patché)
        for p in team:
            if 11 in {p.get("spell1Id"), p.get("spell2Id")}:
                return p
        # Dernier recours : index 1 (ordre Riot : TOP=0, JGL=1, MID=2, BOT=3, SUP=4)
        return team[1] if len(team) > 1 else None

    jg_blue = find_jungler(blue_team)
    jg_red  = find_jungler(red_team)

    logger.info(f"   🎯 Odds JG — blue: {jg_blue.get('championName') if jg_blue else '?'} | red: {jg_red.get('championName') if jg_red else '?'}")

    # Fetch stats en parallèle
    async def get_score(player: dict | None) -> float:
        if not player or not player.get("puuid"):
            return 0.50
        try:
            stats = await asyncio.wait_for(
                get_player_stats(player["puuid"], region, player.get("championName")),
                timeout=8.0,
            )
            return (
                stats["winrate_global"] * 0.40 +
                stats["winrate_champ"]  * 0.35 +
                stats["forme_5"]        * 0.25
            )
        except Exception:
            return 0.50

    score_blue, score_red = await asyncio.gather(
        get_score(jg_blue),
        get_score(jg_red),
    )

    total     = score_blue + score_red
    prob_blue = _clamp(score_blue / total, 0.25, 0.75) if total > 0 else 0.50
    prob_red  = 1.0 - prob_blue

    odds_blue = round(_clamp((1.0 / prob_blue) * 0.90, 1.30, 4.50), 2)
    odds_red  = round(_clamp((1.0 / prob_red)  * 0.90, 1.30, 4.50), 2)

    return {
        "blue": odds_blue,
        "red":  odds_red,
    }

async def compute_live_odds(
    blue_team: list[dict],
    red_team:  list[dict],
    region:    str = "EUW",
) -> dict:
    """
    Point d'entrée principal.
    Retourne un dict complet des côtes pour une game live.

    Structure retournée :
    {
        "who_wins": { "blue": 1.85, "red": 2.10 },
        "first_blood":            { "odds": 8.0  },
        "first_tower":            { "blue": 2.5, "red": 2.5 },
        "first_dragon":           { "blue": 2.5, "red": 2.5 },
        "first_baron":            { "blue": 3.0, "red": 3.0 },
        "game_duration_under25":  { "odds": 2.8  },
        "game_duration_25_35":    { "odds": 1.8  },
        "game_duration_over35":   { "odds": 2.5  },
        "player_positive_kda":    { "odds": 2.2  },
        "prob_blue": 0.54,
        "prob_red":  0.46,
        "detail_blue": [...],
        "detail_red":  [...],
    }
    """
    # Calcul des scores en parallèle
    (score_blue, detail_blue), (score_red, detail_red) = await asyncio.gather(
        _team_score(blue_team, region),
        _team_score(red_team,  region),
    )

    # Probabilités
    total      = score_blue + score_red
    prob_blue  = _clamp(score_blue / total, 0.20, 0.80) if total > 0 else 0.50
    prob_red   = 1.0 - prob_blue

    # Côtes victoire dynamiques
    odds_blue = round(_clamp((1.0 / prob_blue) * MARGIN, MIN_ODDS, MAX_ODDS), 2)
    odds_red  = round(_clamp((1.0 / prob_red)  * MARGIN, MIN_ODDS, MAX_ODDS), 2)

    # Côtes objectifs : légère pondération par favori
    # Ex: si Blue est favori à 60%, premier dragon Blue = 2.3 au lieu de 2.5
    favor_blue = prob_blue - 0.50   # [-0.30, +0.30]

    def obj_odds(base: float, favor: float, side: str) -> float:
        """Ajuste légèrement la cote d'objectif selon le favori."""
        adj = base - (favor * 0.6 if side == "blue" else -favor * 0.6)
        return round(_clamp(adj, 1.30, base + 0.5), 2)

    jg_odds = await compute_jungle_gap_odds(blue_team, red_team, region)

    return {
        "who_wins":              { "blue": odds_blue, "red": odds_red },
        "first_tower":           { "blue": obj_odds(FIXED_ODDS["first_tower"],  favor_blue, "blue"), "red": obj_odds(FIXED_ODDS["first_tower"],  favor_blue, "red") },
        "first_dragon":          { "blue": obj_odds(FIXED_ODDS["first_dragon"], favor_blue, "blue"), "red": obj_odds(FIXED_ODDS["first_dragon"], favor_blue, "red") },
        "first_baron":           { "blue": obj_odds(FIXED_ODDS["first_baron"],  favor_blue, "blue"), "red": obj_odds(FIXED_ODDS["first_baron"],  favor_blue, "red") },
        "first_blood":           FIXED_ODDS["first_blood"],
        "game_duration_under25": FIXED_ODDS["game_duration_under25"],
        "game_duration_25_35":   FIXED_ODDS["game_duration_25_35"],
        "game_duration_over35":  FIXED_ODDS["game_duration_over35"],
        "player_positive_kda":   FIXED_ODDS["player_positive_kda"],
        "champion_kda_over25":   FIXED_ODDS["champion_kda_over25"],
        "champion_kda_over5":    FIXED_ODDS["champion_kda_over5"],
        "champion_kda_over10":   FIXED_ODDS["champion_kda_over10"],
        "top_damage":            FIXED_ODDS["top_damage"],
        "jungle_gap":            jg_odds,
        "prob_blue":    round(prob_blue, 3),
        "prob_red":     round(prob_red,  3),
        "score_blue":   round(score_blue, 4),
        "score_red":    round(score_red,  4),
        "detail_blue":  detail_blue,
        "detail_red":   detail_red,
    }