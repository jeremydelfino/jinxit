import asyncio
import logging
import time
import httpx
from dotenv import load_dotenv
import os

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

import models.user
import models.card
import models.player
import models.match
import models.live_game
import models.bet
import models.bet_type
import models.transaction
import models.user_card
import models.pro_player
import models.favorite
import models.notification

from database import SessionLocal
from models.pro_player import ProPlayer
from models.live_game import LiveGame
from models.bet import Bet
from models.user import User
from models.transaction import Transaction
from models.favorite import UserFavorite
from models.notification import Notification
from services.riot import get_live_game_by_puuid, get_match_result
from services.live_odds_engine import compute_live_odds, FIXED_ODDS
from services.role_detector import assign_roles, ROLE_MAP

logger = logging.getLogger(__name__)

load_dotenv()
RIOT_API_KEY = os.getenv("RIOT_API_KEY")

CHAMP_VERSION = "14.24.1"

# ──────────────────────────────────────────────────────────────
# CHAMPION MAPPING
# ──────────────────────────────────────────────────────────────

_champ_id_to_name:   dict[int, str]       = {}
_champ_name_to_tags: dict[str, list[str]] = {}

async def load_champion_mapping():
    global _champ_id_to_name, _champ_name_to_tags
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            versions = await client.get("https://ddragon.leagueoflegends.com/api/versions.json")
            latest   = versions.json()[0]
            resp     = await client.get(
                f"https://ddragon.leagueoflegends.com/cdn/{latest}/data/en_US/champion.json"
            )
            data = resp.json()
        _champ_id_to_name   = {int(v["key"]): v["id"] for v in data["data"].values()}
        _champ_name_to_tags = {v["id"]: v["tags"]     for v in data["data"].values()}
        logger.info(f"✅ Champion mapping chargé v{latest} — {len(_champ_id_to_name)} champions")
    except Exception as e:
        logger.error(f"❌ Erreur chargement champion mapping: {e}")

def get_champ_name(champ_id: int) -> str:
    return _champ_id_to_name.get(champ_id, "")

def _resolve_champ_name(p: dict) -> str:
    """
    Résout le nom du champion depuis p['championName'] ou p['championId'].
    Utilise le mapping DDragon si le nom est absent/vide.
    """
    name = p.get("championName", "")
    if name and name != "Unknown":
        return name.strip()
    champ_id = p.get("championId")
    if champ_id:
        resolved = get_champ_name(champ_id)
        if resolved:
            return resolved
    return ""

# ──────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────

def extract_summoner_name(p: dict) -> str:
    riot_id = p.get("riotId", "")
    if riot_id:
        return riot_id.split("#")[0]
    return (
        p.get("riotIdGameName") or
        p.get("gameName")       or
        p.get("summonerName")   or
        ""
    )

# ──────────────────────────────────────────────────────────────
# HISTORIQUE RÔLES (MATCH-V5)
# ──────────────────────────────────────────────────────────────

_role_history_cache: dict[str, tuple[str, float]] = {}
ROLE_HISTORY_TTL = 600  # 10 minutes

REGION_TO_REGIONAL = {
    "EUW":  "europe", "EUW1": "europe",
    "EUNE": "europe",
    "KR":   "asia",   "JP":   "asia",
    "NA":   "americas", "NA1": "americas",
    "BR":   "americas", "BR1": "americas",
    "LAN":  "americas", "LAS": "americas",
    "OC":   "sea",    "OC1":  "sea",
}

async def get_recent_role(puuid: str, region: str) -> str | None:
    regional = REGION_TO_REGIONAL.get(region.upper(), "europe")
    url      = f"https://{regional}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                url,
                params  = {"count": 5, "queue": 420},
                headers = {"X-Riot-Token": RIOT_API_KEY},
            )
            match_ids = resp.json()
            if not match_ids or not isinstance(match_ids, list):
                return None

            role_counts: dict[str, int] = {}
            for match_id in match_ids:
                m    = await client.get(
                    f"https://{regional}.api.riotgames.com/lol/match/v5/matches/{match_id}",
                    headers={"X-Riot-Token": RIOT_API_KEY},
                )
                data = m.json()
                for p in data.get("info", {}).get("participants", []):
                    if p.get("puuid") == puuid:
                        pos    = p.get("teamPosition") or p.get("individualPosition") or ""
                        mapped = ROLE_MAP.get(pos.upper())
                        if mapped:
                            role_counts[mapped] = role_counts.get(mapped, 0) + 1
                        break

            if not role_counts:
                return None
            best = max(role_counts, key=role_counts.get)
            logger.info(f"  📈 Historique {puuid[:8]}… → {role_counts} → {best}")
            return best

    except Exception as e:
        logger.warning(f"get_recent_role {puuid[:8]}…: {e}")
        return None

async def get_cached_recent_role(puuid: str, region: str) -> str | None:
    now = time.time()
    if puuid in _role_history_cache:
        role, ts = _role_history_cache[puuid]
        if now - ts < ROLE_HISTORY_TTL:
            return role
    role = await get_recent_role(puuid, region)
    if role:
        _role_history_cache[puuid] = (role, now)
    return role

async def build_history_map(raw: list, region: str) -> dict[str, str]:
    puuids  = [p.get("puuid") for p in raw if p.get("puuid")]
    results = await asyncio.gather(
        *[get_cached_recent_role(puuid, region) for puuid in puuids],
        return_exceptions=True,
    )
    return {
        puuid: role
        for puuid, role in zip(puuids, results)
        if isinstance(role, str)
    }

# ──────────────────────────────────────────────────────────────
# BUILD TEAMS
# ──────────────────────────────────────────────────────────────

async def build_teams(
    participants:      list,
    pro_puuid_to_role: dict,
    region:            str = "EUW",
) -> tuple[list, list]:
    if not participants:
        return [], []

    blue_raw = [p for p in participants if p.get("teamId") == 100]
    red_raw  = [p for p in participants if p.get("teamId") == 200]

    if not blue_raw or not red_raw:
        logger.warning(f"Teams invalides — blue={len(blue_raw)}, red={len(red_raw)}")
        return [], []

    blue_history, red_history = await asyncio.gather(
        build_history_map(blue_raw, region),
        build_history_map(red_raw,  region),
    )

    def build_side(raw: list, history_map: dict) -> list:
        # ── Enrichissement : résoudre championName depuis championId ──
        enriched = []
        for p in raw:
            champ_name = _resolve_champ_name(p)
            if not champ_name:
                logger.warning(
                    f"   ⚠️  championName vide pour championId={p.get('championId')} "
                    f"(mapping: {len(_champ_id_to_name)} entrées)"
                )
            enriched.append({**p, "championName": champ_name})

        # ── Assignation des rôles via role_detector ───────────────────
        try:
            fallback_roles = assign_roles(
                enriched,
                champ_tag_map = _champ_name_to_tags,
                history_map   = history_map,
                pro_role_map  = pro_puuid_to_role,   # ← biais fort, mais l'algo garantit l'unicité
            )
        except Exception as e:
            logger.error(f"Erreur assign_roles: {e}", exc_info=True)
            fallback_roles = []

        result = []
        for i, p in enumerate(enriched):
            puuid      = p.get("puuid") or ""
            champ_name = p.get("championName") or "Unknown"
            champ_id   = p.get("championId")

            # assign_roles intègre déjà le biais pro_role → résultat unique garanti
            if i < len(fallback_roles) and fallback_roles[i]:
                role = ROLE_MAP.get(fallback_roles[i].upper(), "FILL")
            else:
                role = "FILL"

            result.append({
                "puuid":        puuid,
                "summonerName": extract_summoner_name(p),
                "championId":   champ_id,
                "championName": champ_name,
                "teamId":       p.get("teamId"),
                "role":         role,
                "spell1Id":     p.get("spell1Id"),
                "spell2Id":     p.get("spell2Id"),
            })
        return result

    return build_side(blue_raw, blue_history), build_side(red_raw, red_history)


def patch_team(team: list, puuid_to_participant: dict, pro_puuid_to_role: dict) -> list:
    """
    Re-enrichit une team déjà en DB avec les données live :
    - Résout championName depuis championId si vide
    - Recalcule les rôles via assign_roles avec les tags DDragon
    - Met à jour summonerName et spells depuis la game live
    """
    # ── Construire la liste enrichie pour assign_roles ────────
    enriched_for_roles = []
    for p in team:
        puuid  = p.get("puuid", "")
        live_p = puuid_to_participant.get(puuid, {})

        champ_id   = p.get("championId") or live_p.get("championId")
        champ_name = (
            p.get("championName") or
            live_p.get("championName") or
            (get_champ_name(champ_id) if champ_id else "")
        )
        # Nettoyage
        if champ_name == "Unknown":
            champ_name = get_champ_name(champ_id) if champ_id else ""

        enriched_for_roles.append({
            **p,
            "championName": champ_name,
            "spell1Id":     live_p.get("spell1Id") or p.get("spell1Id"),
            "spell2Id":     live_p.get("spell2Id") or p.get("spell2Id"),
        })

    # ── assign_roles avec tags DDragon ────────────────────────
    try:
        spell_roles = assign_roles(
            enriched_for_roles,
            champ_tag_map = _champ_name_to_tags,
            pro_role_map  = pro_puuid_to_role,   # ← idem, biais fort résolu globalement
        )
    except Exception as e:
        logger.error(f"Erreur assign_roles (patch): {e}", exc_info=True)
        spell_roles = []

    # ── Construire le résultat final ──────────────────────────
    result = []
    for i, p in enumerate(team):
        puuid  = p.get("puuid", "")
        live_p = puuid_to_participant.get(puuid, {})

        champ_id   = p.get("championId") or live_p.get("championId")
        champ_name = enriched_for_roles[i]["championName"] if i < len(enriched_for_roles) else ""

# assign_roles intègre déjà le biais pro_role → résultat unique garanti
        if i < len(spell_roles) and spell_roles[i]:
            role = ROLE_MAP.get(spell_roles[i].upper(), "FILL")
        else:
            role = "FILL"

        result.append({
            **p,
            "summonerName": extract_summoner_name(live_p) or p.get("summonerName", ""),
            "championId":   champ_id,
            "championName": champ_name or p.get("championName", ""),
            "spell1Id":     live_p.get("spell1Id") or p.get("spell1Id"),
            "spell2Id":     live_p.get("spell2Id") or p.get("spell2Id"),
            "role":         role,
        })
    return result


def needs_patch(team: list) -> bool:
    """
    Retourne True si la team a besoin d'être re-patchée :
    - summonerName manquant
    - spell1Id manquant
    - championName manquant ou vide
    - rôle null/FILL alors qu'on pourrait mieux faire
    """
    return any(
        not p.get("summonerName")
        or p.get("spell1Id") is None
        or not p.get("championName")
        or p.get("championName") == "Unknown"
        or p.get("role") is None
        or p.get("role") == "FILL"
        for p in team
    )

# ──────────────────────────────────────────────────────────────
# NOTIFICATIONS FAVORIS
# ──────────────────────────────────────────────────────────────

def notify_favorites_for_game(db: Session, pro: ProPlayer, new_game: LiveGame):
    from models.player import SearchedPlayer

    searched_player = db.query(SearchedPlayer).filter(
        SearchedPlayer.riot_puuid == pro.riot_puuid
    ).first()
    if not searched_player:
        return

    fans = db.query(UserFavorite).filter(
        UserFavorite.riot_player_id == searched_player.id
    ).all()
    if not fans:
        return

    for fan in fans:
        already_notified = db.query(Notification).filter(
            Notification.user_id == fan.user_id,
            Notification.type    == "favorite_live",
            Notification.data["live_game_id"].astext == str(new_game.id),
        ).first()
        if not already_notified:
            db.add(Notification(
                user_id = fan.user_id,
                type    = "favorite_live",
                message = f"{searched_player.summoner_name} vient de lancer une partie !",
                data    = {
                    "live_game_id":  new_game.id,
                    "riot_game_id":  new_game.riot_game_id,
                    "summoner_name": searched_player.summoner_name,
                    "tag_line":      searched_player.tag_line,
                    "region":        searched_player.region,
                },
            ))
            logger.info(f"   🔔 Notif envoyée à user {fan.user_id} pour {searched_player.summoner_name}")

# ──────────────────────────────────────────────────────────────
# CALCUL CÔTES EN BACKGROUND
# ──────────────────────────────────────────────────────────────

async def _compute_and_save_odds(game_id: int, blue_team: list, red_team: list, region: str):
    db = SessionLocal()
    try:
        odds_data = await asyncio.wait_for(
            compute_live_odds(blue_team, red_team, region=region),
            timeout=30.0,
        )
        game = db.query(LiveGame).filter(LiveGame.id == game_id).first()
        if game:
            game.odds_data = odds_data
            db.commit()
            logger.info(f"   📊 Côtes sauvegardées game {game_id} → Blue ×{odds_data['who_wins']['blue']} / Red ×{odds_data['who_wins']['red']}")
    except asyncio.TimeoutError:
        logger.warning(f"   ⚠️  Odds engine timeout pour game {game_id}")
    except Exception as e:
        logger.error(f"   ⚠️  Odds engine error game {game_id}: {e}")
    finally:
        db.close()

# ──────────────────────────────────────────────────────────────
# RÉSOLUTION DES PARIS
# ──────────────────────────────────────────────────────────────

async def resolve_bets_for_game(game_id: int, riot_game_id: str, region: str):
    """
    Résout tous les paris pending d'une game.
    Logique :
      1. Tente de récupérer le résultat MATCH-V5 (jusqu'à 8 tentatives sur 15min).
      2. Si trouvé → won/lost selon bet_type_slug.
      3. Si non trouvé après tous les retries → cancelled + remboursement.
      4. bet_value est NORMALISÉ en lowercase pour comparaison ("blue" / "red").
    """
    db: Session = SessionLocal()
    try:
        game = db.query(LiveGame).filter(LiveGame.id == game_id).first()
        if not game:
            logger.warning(f"resolve_bets: game {game_id} introuvable")
            return

        # ── Retry MATCH-V5 — élargi à 8 tentatives, ~15min total ─
        result = None
        RETRY_DELAYS = [10, 30, 60, 90, 120, 180, 240, 300]  # = 1020s = 17min
        for attempt, delay in enumerate(RETRY_DELAYS):
            logger.info(f"   🔍 Tentative {attempt + 1}/{len(RETRY_DELAYS)} MATCH-V5 pour {riot_game_id}...")
            result = await get_match_result("", riot_game_id, region)
            if result:
                logger.info(f"   ✅ MATCH-V5 disponible dès la tentative {attempt + 1}")
                break
            if attempt < len(RETRY_DELAYS) - 1:
                await asyncio.sleep(delay)

        pending_bets = db.query(Bet).filter(
            Bet.live_game_id == game_id,
            Bet.status       == "pending",
        ).all()

        if not pending_bets:
            logger.info(f"   ℹ️  Aucun pari pending pour game {game_id}")
            return

        # ── Si pas de résultat → on rembourse, mais on log MASSIVEMENT ─
        if not result:
            logger.error(
                f"   ❌ MATCH-V5 indisponible après {len(RETRY_DELAYS)} tentatives — "
                f"game {game_id} riot_id={riot_game_id} region={region} → REMBOURSEMENT"
            )
            for bet in pending_bets:
                bet.status = "cancelled"
                user = db.query(User).filter(User.id == bet.user_id).with_for_update().first()
                if user:
                    user.coins += bet.amount
                    db.add(Transaction(
                        user_id=user.id, type="bet_refunded", amount=bet.amount,
                        description=f"Pari annulé (MATCH-V5 timeout après 17min) — remboursement de {bet.amount}",
                    ))
                logger.info(f"   ↩️  Bet {bet.id} remboursé ({bet.amount} coins)")
            db.commit()
            return

        # ── Résultat disponible ──────────────────────────────────
        winner_team       = (result.get("winner_team")       or "").lower()
        first_blood       = (result.get("first_blood")       or "").lower() if result.get("first_blood") else None
        first_tower_side  = (result.get("first_tower_side")  or "").lower() if result.get("first_tower_side") else None
        first_dragon_side = (result.get("first_dragon_side") or "").lower() if result.get("first_dragon_side") else None
        first_baron_side  = (result.get("first_baron_side")  or "").lower() if result.get("first_baron_side") else None
        duration_min      = result.get("duration_min", 0)
        kda_positive      = result.get("kda_positive",     {})
        player_stats      = result.get("player_stats",     {})
        top_damage_champ  = result.get("top_damage_champ", None)
        jungle_gap_side   = (result.get("jungle_gap_side") or "").lower() if result.get("jungle_gap_side") else None

        if not winner_team:
            logger.error(f"   ❌ winner_team vide pour game {game_id} — REMBOURSEMENT")
            for bet in pending_bets:
                bet.status = "cancelled"
                user = db.query(User).filter(User.id == bet.user_id).with_for_update().first()
                if user:
                    user.coins += bet.amount
                    db.add(Transaction(
                        user_id=user.id, type="bet_refunded", amount=bet.amount,
                        description="Pari annulé (résultat ambigu) — remboursement",
                    ))
            db.commit()
            return

        logger.info(
            f"   🏆 winner={winner_team} | fb={first_blood} | tower={first_tower_side} | "
            f"dragon={first_dragon_side} | baron={first_baron_side} | duration={duration_min:.1f}min | "
            f"top_dmg={top_damage_champ} | jg_gap={jungle_gap_side}"
        )

        # Mapping puuid → champ pour les paris liés à un champion
        all_players    = (game.blue_team or []) + (game.red_team or [])
        puuid_by_champ = {}
        champ_by_puuid = {}
        for p in all_players:
            puuid = p.get("puuid", "")
            if not puuid:
                continue
            champ = p.get("championName", "")
            if not champ or champ == "Unknown":
                champ_id = p.get("championId")
                if champ_id:
                    champ = get_champ_name(champ_id)
            if champ:
                puuid_by_champ[champ.lower()] = puuid
                champ_by_puuid[puuid] = champ

        # ── Résolution pari par pari ─────────────────────────────
        for bet in pending_bets:
            slug          = bet.bet_type_slug
            bet_value     = (bet.bet_value or "").lower().strip()
            won           = False
            refund_reason = None

            if slug == "who_wins":
                won = (bet_value == winner_team)

            elif slug == "first_blood":
                if first_blood is None:
                    refund_reason = "First blood non détecté dans cette partie"
                else:
                    won = (bet_value == first_blood)

            elif slug == "first_tower":
                if first_tower_side is None:
                    refund_reason = "First tower non détectée"
                else:
                    won = (bet_value == first_tower_side)

            elif slug == "first_dragon":
                if first_dragon_side is None:
                    refund_reason = "First dragon non détecté"
                else:
                    won = (bet_value == first_dragon_side)

            elif slug == "first_baron":
                if first_baron_side is None:
                    refund_reason = "First baron non détecté (game trop courte ?)"
                else:
                    won = (bet_value == first_baron_side)

            elif slug == "game_duration_under25":
                won = (duration_min < 25)
            elif slug == "game_duration_25_35":
                won = (25 <= duration_min < 35)
            elif slug == "game_duration_over35":
                won = (duration_min >= 35)

            elif slug == "player_positive_kda":
                target_puuid = puuid_by_champ.get(bet_value)
                if not target_puuid:
                    refund_reason = f"Champion {bet.bet_value} introuvable dans la partie"
                else:
                    won = bool(kda_positive.get(target_puuid, False))

            elif slug in ("champion_kda_over25", "champion_kda_over5", "champion_kda_over10"):
                threshold = {"champion_kda_over25": 2.5, "champion_kda_over5": 5.0, "champion_kda_over10": 10.0}[slug]
                target_puuid = puuid_by_champ.get(bet_value)
                if not target_puuid:
                    refund_reason = f"Champion {bet.bet_value} introuvable"
                else:
                    stats = player_stats.get(target_puuid, {})
                    kda   = stats.get("kda", 0)
                    won   = (kda >= threshold)

            elif slug == "top_damage":
                if not top_damage_champ:
                    refund_reason = "Top damage non détecté"
                else:
                    won = (bet_value == top_damage_champ.lower())

            elif slug == "jungle_gap":
                if jungle_gap_side is None or jungle_gap_side == "none":
                    refund_reason = "Aucun Jungle Gap significatif détecté"
                else:
                    won = (bet_value == jungle_gap_side)

            else:
                refund_reason = f"Type de pari inconnu : {slug}"

            # ── Application du résultat ──────────────────────────
            if refund_reason:
                bet.status = "cancelled"
                user = db.query(User).filter(User.id == bet.user_id).with_for_update().first()
                if user:
                    user.coins += bet.amount
                    db.add(Transaction(
                        user_id=user.id, type="bet_refunded", amount=bet.amount,
                        description=f"Pari annulé — {refund_reason}",
                    ))
                logger.info(f"   ↩️  Bet {bet.id} remboursé — {refund_reason}")
                continue

            if won:
                stored_odds = getattr(bet, "odds", None)
                multiplier  = float(stored_odds) if stored_odds and float(stored_odds) > 1 else FIXED_ODDS.get(slug, 2.0)
                multiplier *= (1 + (bet.boost_applied or 0) / 100)
                payout      = int(bet.amount * multiplier)
                bet.status  = "won"
                bet.payout  = payout
                user = db.query(User).filter(User.id == bet.user_id).with_for_update().first()
                if user:
                    user.coins += payout
                    db.add(Transaction(
                        user_id=user.id, type="bet_won", amount=payout,
                        description=f"Pari gagné — {slug}: {bet.bet_value} (×{multiplier:.2f})",
                    ))
                logger.info(f"   ✅ Bet {bet.id} GAGNÉ → +{payout} coins (×{multiplier:.2f})")
            else:
                bet.status = "lost"
                bet.payout = 0
                logger.info(f"   ❌ Bet {bet.id} PERDU ({slug}: misait '{bet.bet_value}', réel='{winner_team}')")

        db.commit()
        logger.info(f"   ✅ {len(pending_bets)} pari(s) résolus pour game {game_id}")

    except Exception as e:
        logger.error(f"   ❌ Erreur resolve_bets game {game_id}: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()

# ──────────────────────────────────────────────────────────────
# POLL PRINCIPAL
# ──────────────────────────────────────────────────────────────

async def poll_pro_games():
    # ── Garantir le champion mapping avant tout ───────────────
    if not _champ_id_to_name:
        logger.info("📚 Champion mapping absent — chargement forcé...")
        await load_champion_mapping()

    if not _champ_id_to_name:
        logger.error("❌ Champion mapping toujours vide après chargement — poll annulé")
        return

    db: Session = SessionLocal()
    try:
        pros = db.query(ProPlayer).filter(
            ProPlayer.riot_puuid != None,
            ProPlayer.is_active  == True,
        ).all()

        logger.info(f"🎮 Poll: vérification de {len(pros)} pros...")

        pro_puuid_to_role: dict[str, str] = {
            p.riot_puuid: p.role
            for p in pros
            if p.riot_puuid and p.role
        }

        puuids_in_game     = set()
        processed_game_ids = set()

        for pro in pros:
            try:
                live = await get_live_game_by_puuid(pro.riot_puuid, pro.region)
                if not live:
                    await asyncio.sleep(1.5)
                    continue

                riot_game_id = str(live.get("gameId"))
                puuids_in_game.add(pro.riot_puuid)

                if riot_game_id in processed_game_ids:
                    await asyncio.sleep(1.5)
                    continue
                processed_game_ids.add(riot_game_id)

                participants         = live.get("participants", [])
                puuid_to_participant = {p.get("puuid"): p for p in participants}

                existing = db.query(LiveGame).filter(
                    LiveGame.riot_game_id == riot_game_id
                ).first()

                if not existing:
                    try:
                        blue_team, red_team = await build_teams(
                            participants, pro_puuid_to_role, region=pro.region
                        )

                        if len(blue_team) < 3 or len(red_team) < 3:
                            logger.warning(
                                f"   ⚠️ Game {riot_game_id} ignorée — "
                                f"teams invalides (blue={len(blue_team)}, red={len(red_team)})"
                            )
                            await asyncio.sleep(1.5)
                            continue

                        new_game = LiveGame(
                            searched_player_id = 1,
                            riot_game_id       = riot_game_id,
                            queue_type         = str(live.get("gameQueueConfigId", "")),
                            blue_team          = blue_team,
                            red_team           = red_team,
                            duration_seconds   = live.get("gameLength", 0),
                            status             = "live",
                            region             = pro.region,
                        )
                        db.add(new_game)
                        db.flush()

                        asyncio.create_task(
                            _compute_and_save_odds(new_game.id, blue_team, red_team, pro.region)
                        )

                        db.commit()
                        notify_favorites_for_game(db, pro, new_game)
                        logger.info(f"   ✅ Nouvelle partie: {pro.name} ({riot_game_id})")

                    except Exception as e:
                        db.rollback()
                        logger.warning(f"   ⚠️ Game {riot_game_id} erreur insertion: {e}")

                else:
                    existing.duration_seconds = live.get("gameLength", 0)

                    if existing.status == "ended":
                        existing.status = "live"

                    blue_needs = needs_patch(existing.blue_team or [])
                    red_needs  = needs_patch(existing.red_team  or [])

                    if blue_needs or red_needs:
                        new_blue = patch_team(existing.blue_team or [], puuid_to_participant, pro_puuid_to_role)
                        new_red  = patch_team(existing.red_team  or [], puuid_to_participant, pro_puuid_to_role)
                        existing.blue_team = new_blue
                        existing.red_team  = new_red
                        flag_modified(existing, "blue_team")
                        flag_modified(existing, "red_team")
                        logger.info(f"   🔄 Champions + noms + rôles patchés pour game {riot_game_id}")

                    try:
                        db.commit()
                    except Exception as e:
                        db.rollback()
                        logger.warning(f"   ⚠️ Erreur commit update game {riot_game_id}: {e}")

                await asyncio.sleep(1.5)

            except Exception as e:
                logger.error(f"   ❌ Erreur pour {pro.name}: {e}")
                continue

        # ── Détection games terminées ─────────────────────────
        active_games     = db.query(LiveGame).filter(LiveGame.status == "live").all()
        games_to_resolve = []

        for game in active_games:
            if game.riot_game_id in processed_game_ids:
                continue

            game.status = "ended"
            logger.info(f"   🏁 Game {game.riot_game_id} marquée ENDED")

            has_pending = db.query(Bet).filter(
                Bet.live_game_id == game.id,
                Bet.status       == "pending",
            ).first()

            if has_pending:
                all_puuids = [
                    p.get("puuid")
                    for p in (game.blue_team or []) + (game.red_team or [])
                    if p.get("puuid")
                ]
                pro_match = db.query(ProPlayer).filter(
                    ProPlayer.riot_puuid.in_(all_puuids)
                ).first()
                if pro_match:
                    region = pro_match.region
                elif game.region:
                    region = game.region
                else:
                    # Fallback : chercher via SearchedPlayer lié à la game
                    from models.player import SearchedPlayer
                    searched = db.query(SearchedPlayer).filter(
                        SearchedPlayer.id == game.searched_player_id
                    ).first()
                    if searched:
                        region = searched.region
                    else:
                        region = "KR" if str(game.riot_game_id).startswith("8") else "EUW"
                games_to_resolve.append((game.id, game.riot_game_id, region))

        db.commit()

        for gid, rgid, reg in games_to_resolve:
            logger.info(f"   🎯 Résolution background lancée pour game {gid}")
            asyncio.create_task(resolve_bets_for_game(gid, rgid, reg))

        logger.info(f"✅ Poll terminé — {len(puuids_in_game)} pros en game")

    except Exception as e:
        logger.error(f"❌ Erreur poll global: {e}")
        db.rollback()
    finally:
        db.close()