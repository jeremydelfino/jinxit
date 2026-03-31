import asyncio
import logging
import httpx

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

logger = logging.getLogger(__name__)

CHAMP_VERSION = "14.24.1"

# ──────────────────────────────────────────────────────────────
# CHAMPION ID → NAME MAPPING
# ──────────────────────────────────────────────────────────────

_champ_id_to_name: dict[int, str] = {}

async def load_champion_mapping():
    global _champ_id_to_name
    url = f"https://ddragon.leagueoflegends.com/cdn/{CHAMP_VERSION}/data/en_US/champion.json"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            data = resp.json()
        _champ_id_to_name = {
            int(v["key"]): v["id"]
            for v in data["data"].values()
        }
        logger.info(f"✅ Champion mapping chargé — {len(_champ_id_to_name)} champions")
    except Exception as e:
        logger.error(f"❌ Erreur chargement champion mapping: {e}")

def get_champ_name(champ_id: int) -> str:
    return _champ_id_to_name.get(champ_id, "")


# ──────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────

def extract_summoner_name(p: dict) -> str:
    riot_id = p.get("riotId", "")
    if riot_id:
        return riot_id.split("#")[0]
    return (
        p.get("riotIdGameName") or
        p.get("gameName") or
        p.get("summonerName") or
        ""
    )

SMITE = 11

# Ordre canonique des rôles en Spectator V5 (position dans la liste par teamId)
# Riot retourne les participants dans cet ordre : TOP, JGL, MID, BOT, SUP
ROLE_BY_INDEX = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]

def detect_role_live(p: dict, team_index: int) -> str:
    """
    Détecte le rôle d'un joueur depuis les données Spectator V5.
    Priorité :
      1. Smite → JUNGLE (100% fiable)
      2. DB ProPlayer (si PUUID connu) → géré en amont dans build_teams
      3. Index dans la liste (ordre Riot : TOP/JGL/MID/BOT/SUP)
    """
    spells = {p.get("spell1Id"), p.get("spell2Id")}
    if SMITE in spells:
        return "JUNGLE"
    # Fallback : position dans la liste de l'équipe (0→TOP, 1→JGL, 2→MID, 3→BOT, 4→SUP)
    if 0 <= team_index < len(ROLE_BY_INDEX):
        return ROLE_BY_INDEX[team_index]
    return ""

def build_participant(p: dict, team_index: int, pro_role: str | None = None) -> dict:
    """
    Construit un participant pour le stockage en DB depuis les données Spectator V5.
    pro_role : rôle issu de la DB ProPlayer si le joueur est un pro connu.
    """
    champ_id   = p.get("championId")
    champ_name = p.get("championName") or (get_champ_name(champ_id) if champ_id else "")
    spells     = {p.get("spell1Id"), p.get("spell2Id")}

    # Priorité rôle : pro_role (DB) > Smite > index
    if pro_role:
        role = pro_role
    elif SMITE in spells:
        role = "JUNGLE"
    else:
        role = ROLE_BY_INDEX[team_index] if 0 <= team_index < len(ROLE_BY_INDEX) else ""

    return {
        "puuid":        p.get("puuid") or "",
        "summonerName": extract_summoner_name(p),
        "championId":   champ_id,
        "championName": champ_name,
        "teamId":       p.get("teamId"),
        "role":         role,
        "spell1Id":     p.get("spell1Id"),
        "spell2Id":     p.get("spell2Id"),
    }

def build_teams(participants: list, pro_puuid_to_role: dict) -> tuple[list, list]:
    """
    Construit blue_team et red_team depuis les participants Spectator V5.
    pro_puuid_to_role : { puuid: role } pour les pros connus en DB.
    Conserve l'index dans la liste de chaque équipe pour le fallback de rôle.
    """
    blue_raw = [p for p in participants if p.get("teamId") == 100]
    red_raw  = [p for p in participants if p.get("teamId") == 200]

    blue_team = [
        build_participant(p, i, pro_puuid_to_role.get(p.get("puuid")))
        for i, p in enumerate(blue_raw)
    ]
    red_team = [
        build_participant(p, i, pro_puuid_to_role.get(p.get("puuid")))
        for i, p in enumerate(red_raw)
    ]
    return blue_team, red_team

def patch_team(team: list, puuid_to_participant: dict, pro_puuid_to_role: dict) -> list:
    result = []
    for i, p in enumerate(team):
        live_p     = puuid_to_participant.get(p.get("puuid"), {})
        champ_id   = p.get("championId") or live_p.get("championId")
        champ_name = p.get("championName") or live_p.get("championName") or (get_champ_name(champ_id) if champ_id else "")
        spells     = {live_p.get("spell1Id"), live_p.get("spell2Id")}

        puuid = p.get("puuid", "")
        if pro_puuid_to_role.get(puuid):
            role = pro_puuid_to_role[puuid]
        elif SMITE in spells:
            role = "JUNGLE"
        else:
            role = p.get("role") or (ROLE_BY_INDEX[i] if 0 <= i < len(ROLE_BY_INDEX) else "")

        result.append({
            **p,
            "summonerName": extract_summoner_name(live_p) or p.get("summonerName", ""),
            "championName": champ_name,
            "spell1Id":     live_p.get("spell1Id") or p.get("spell1Id"),
            "spell2Id":     live_p.get("spell2Id") or p.get("spell2Id"),
            "role":         role,
        })
    return result

def needs_patch(team: list) -> bool:
    return any(
        not p.get("summonerName") or p.get("spell1Id") is None or not p.get("championName")
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
    db: Session = SessionLocal()
    try:
        game = db.query(LiveGame).filter(LiveGame.id == game_id).first()
        if not game:
            logger.warning(f"resolve_bets: game {game_id} introuvable")
            return

        # ── 5 tentatives espacées de 60s pour attendre MATCH-V5 ──
        # Note: puuid non utilisé dans get_match_result (appel direct par match ID)
        result = None
        for attempt in range(5):
            logger.info(f"   🔍 Tentative {attempt + 1}/5 MATCH-V5 pour {riot_game_id}...")
            result = await get_match_result("", riot_game_id, region)
            if result:
                break
            if attempt < 4:
                await asyncio.sleep(60)

        pending_bets = db.query(Bet).filter(
            Bet.live_game_id == game_id,
            Bet.status       == "pending",
        ).all()

        if not pending_bets:
            logger.info(f"   ℹ️  Aucun pari pending pour game {game_id}")
            return

        # ── MATCH-V5 indisponible → remboursement total ───────
        if not result:
            logger.error(f"   ❌ MATCH-V5 indisponible après 5 tentatives — remboursement")
            for bet in pending_bets:
                bet.status = "cancelled"
                user = db.query(User).filter(User.id == bet.user_id).with_for_update().first()
                if user:
                    user.coins += bet.amount
                    db.add(Transaction(
                        user_id=user.id,
                        type="bet_refunded",
                        amount=bet.amount,
                        description="Pari annulé (résultat indisponible) — remboursement",
                    ))
            db.commit()
            return

        # ── Extraction des résultats ──────────────────────────
        winner_team       = result.get("winner_team")
        first_blood       = result.get("first_blood")
        first_tower_side  = result.get("first_tower_side")
        first_dragon_side = result.get("first_dragon_side")
        first_baron_side  = result.get("first_baron_side")
        duration_min      = result.get("duration_min", 0)
        kda_positive      = result.get("kda_positive",    {})
        player_stats      = result.get("player_stats",    {})
        top_damage_champ  = result.get("top_damage_champ", None)
        jungle_gap_side   = result.get("jungle_gap_side",  None)

        logger.info(
            f"   🏆 winner={winner_team} | fb={first_blood} | "
            f"tower={first_tower_side} | dragon={first_dragon_side} | "
            f"baron={first_baron_side} | duration={duration_min:.1f}min | "
            f"top_dmg={top_damage_champ} | jg_gap={jungle_gap_side}"
        )

        all_players = (game.blue_team or []) + (game.red_team or [])

        # Index championName (lowercase) → puuid
        puuid_by_champ: dict[str, str] = {
            p.get("championName", "").lower(): p.get("puuid", "")
            for p in all_players
            if p.get("puuid") and p.get("championName")
        }

        # ── Résolution pari par pari ──────────────────────────
        for bet in pending_bets:
            slug = bet.bet_type_slug
            won  = False
            refund_reason = None

            if slug == "who_wins":
                won = (bet.bet_value == winner_team)

            elif slug == "first_blood":
                won = bool(first_blood) and bet.bet_value.lower() == first_blood.lower()

            elif slug == "first_tower":
                won = (bet.bet_value == first_tower_side)

            elif slug == "first_dragon":
                won = (bet.bet_value == first_dragon_side)

            elif slug == "first_baron":
                if first_baron_side is None:
                    refund_reason = "Aucun Baron dans cette partie"
                else:
                    won = (bet.bet_value == first_baron_side)

            elif slug == "game_duration_under25":
                won = duration_min < 25

            elif slug == "game_duration_25_35":
                won = 25 <= duration_min <= 35

            elif slug == "game_duration_over35":
                won = duration_min > 35

            elif slug == "player_positive_kda":
                puuid = puuid_by_champ.get(bet.bet_value.lower())
                if puuid:
                    won = kda_positive.get(puuid, False)
                else:
                    refund_reason = f"Champion introuvable ({bet.bet_value})"

            elif slug == "champion_kda_over25":
                puuid = puuid_by_champ.get(bet.bet_value.lower())
                if puuid:
                    won = player_stats.get(puuid, {}).get("kda", 0) > 2.5
                else:
                    refund_reason = f"Champion introuvable ({bet.bet_value})"

            elif slug == "champion_kda_over5":
                puuid = puuid_by_champ.get(bet.bet_value.lower())
                if puuid:
                    won = player_stats.get(puuid, {}).get("kda", 0) > 5.0
                else:
                    refund_reason = f"Champion introuvable ({bet.bet_value})"

            elif slug == "champion_kda_over10":
                puuid = puuid_by_champ.get(bet.bet_value.lower())
                if puuid:
                    won = player_stats.get(puuid, {}).get("kda", 0) > 10.0
                else:
                    refund_reason = f"Champion introuvable ({bet.bet_value})"

            elif slug == "top_damage":
                if top_damage_champ:
                    won = bet.bet_value.lower() == top_damage_champ.lower()
                else:
                    refund_reason = "Données de dégâts indisponibles"

            elif slug == "jungle_gap":
                if bet.bet_value == "none":
                    won = (jungle_gap_side is None)
                elif jungle_gap_side is None:
                    refund_reason = "Aucun Jungle Gap détecté dans cette partie"
                else:
                    won = (bet.bet_value == jungle_gap_side)

            else:
                refund_reason = f"Type de pari inconnu : {slug}"

            # ── Remboursement ─────────────────────────────────
            if refund_reason:
                bet.status = "cancelled"
                user = db.query(User).filter(User.id == bet.user_id).with_for_update().first()
                if user:
                    user.coins += bet.amount
                    db.add(Transaction(
                        user_id=user.id,
                        type="bet_refunded",
                        amount=bet.amount,
                        description=f"Pari annulé — {refund_reason}",
                    ))
                logger.info(f"   ↩️  Bet {bet.id} remboursé — {refund_reason}")
                continue

            # ── Gagné ─────────────────────────────────────────
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
                        user_id=user.id,
                        type="bet_won",
                        amount=payout,
                        description=f"Pari gagné — {slug}: {bet.bet_value}",
                    ))
                logger.info(f"   ✅ Bet {bet.id} GAGNÉ → +{payout} coins (×{multiplier:.2f})")

            # ── Perdu ──────────────────────────────────────────
            else:
                bet.status = "lost"
                bet.payout = 0
                logger.info(f"   ❌ Bet {bet.id} PERDU ({slug}: misait {bet.bet_value})")

        db.commit()
        logger.info(f"   ✅ {len(pending_bets)} pari(s) résolus pour game {game_id}")

    except Exception as e:
        logger.error(f"   ❌ Erreur resolve_bets game {game_id}: {e}")
        db.rollback()
    finally:
        db.close()


# ──────────────────────────────────────────────────────────────
# POLL PRINCIPAL
# ──────────────────────────────────────────────────────────────

async def poll_pro_games():
    if not _champ_id_to_name:
        await load_champion_mapping()

    db: Session = SessionLocal()
    try:
        pros = db.query(ProPlayer).filter(
            ProPlayer.riot_puuid != None,
            ProPlayer.is_active  == True,
        ).all()

        logger.info(f"🎮 Poll: vérification de {len(pros)} pros...")

        # Map puuid → role pour tous les pros connus en DB
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
                        blue_team, red_team = build_teams(participants, pro_puuid_to_role)

                        if len(blue_team) < 3 or len(red_team) < 3:
                            logger.warning(f"   ⚠️ Game {riot_game_id} ignorée — teams invalides (blue={len(blue_team)}, red={len(red_team)})")
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
                        existing.blue_team = patch_team(existing.blue_team or [], puuid_to_participant, pro_puuid_to_role)
                        existing.red_team  = patch_team(existing.red_team  or [], puuid_to_participant, pro_puuid_to_role)
                        flag_modified(existing, "blue_team")
                        flag_modified(existing, "red_team")
                        logger.info(f"   🔄 Champions + noms + rôles patchés pour game {riot_game_id}")

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
                region = pro_match.region if pro_match else (
                    "KR" if str(game.riot_game_id).startswith("8") else "EUW"
                )
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