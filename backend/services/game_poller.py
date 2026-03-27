import asyncio
import logging

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

from database import SessionLocal
from models.pro_player import ProPlayer
from models.live_game import LiveGame
from models.bet import Bet
from models.user import User
from models.transaction import Transaction
from services.riot import get_live_game_by_puuid, get_match_result

logger = logging.getLogger(__name__)

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


def build_participant(p: dict) -> dict:
    return {
        "puuid":        p.get("puuid") or "",
        "summonerName": extract_summoner_name(p),
        "championId":   p.get("championId"),
        "championName": p.get("championName", ""),
        "teamId":       p.get("teamId"),
        "role":         p.get("individualPosition", "") or p.get("position", "") or "",
        # ✅ Spells nécessaires pour la détection de rôle côté frontend
        "spell1Id":     p.get("spell1Id"),
        "spell2Id":     p.get("spell2Id"),
    }


async def resolve_bets_for_game(game_id: int, riot_game_id: str, region: str):
    db: Session = SessionLocal()
    try:
        game = db.query(LiveGame).filter(LiveGame.id == game_id).first()
        if not game:
            return

        all_players = (game.blue_team or []) + (game.red_team or [])
        ref_puuid = next((p.get("puuid") for p in all_players if p.get("puuid")), None)
        if not ref_puuid:
            logger.warning(f"resolve_bets: pas de puuid pour game {game_id}")
            return

        result = None
        for attempt in range(5):
            logger.info(f"   🔍 Tentative {attempt+1}/5 MATCH-V5 pour {riot_game_id}...")
            result = await get_match_result(ref_puuid, riot_game_id, region)
            if result:
                break
            if attempt < 4:
                await asyncio.sleep(60)

        pending_bets = db.query(Bet).filter(
            Bet.live_game_id == game_id,
            Bet.status == "pending"
        ).all()

        if not pending_bets:
            return

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
                        description="Pari annulé (résultat indisponible) — remboursement"
                    ))
            db.commit()
            return

        winner_team = result.get("winner_team")
        first_blood = result.get("first_blood")
        logger.info(f"   🏆 Résultat: winner={winner_team}, first_blood={first_blood}")

        for bet in pending_bets:
            won = False
            if bet.bet_type_slug == "who_wins":
                won = (bet.bet_value == winner_team)
            elif bet.bet_type_slug == "first_blood":
                won = bool(first_blood) and bet.bet_value.lower() == first_blood.lower()
            else:
                bet.status = "cancelled"
                user = db.query(User).filter(User.id == bet.user_id).with_for_update().first()
                if user:
                    user.coins += bet.amount
                    db.add(Transaction(
                        user_id=user.id,
                        type="bet_refunded",
                        amount=bet.amount,
                        description=f"Pari annulé (type inconnu : {bet.bet_type_slug})"
                    ))
                continue

            if won:
                multiplier = 2.0 * (1 + (bet.boost_applied or 0) / 100)
                payout = int(bet.amount * multiplier)
                bet.status = "won"
                bet.payout = payout
                user = db.query(User).filter(User.id == bet.user_id).with_for_update().first()
                if user:
                    user.coins += payout
                    db.add(Transaction(
                        user_id=user.id,
                        type="bet_won",
                        amount=payout,
                        description=f"Pari gagné — {bet.bet_type_slug}: {bet.bet_value}"
                    ))
                logger.info(f"   ✅ Bet {bet.id} GAGNÉ → +{payout} coins (user {bet.user_id})")
            else:
                bet.status = "lost"
                bet.payout = 0
                logger.info(f"   ❌ Bet {bet.id} PERDU (user {bet.user_id})")

        db.commit()
        logger.info(f"   ✅ {len(pending_bets)} pari(s) résolus pour game {game_id}")

    except Exception as e:
        logger.error(f"   ❌ Erreur resolve_bets game {game_id}: {e}")
        db.rollback()
    finally:
        db.close()


async def poll_pro_games():
    db: Session = SessionLocal()
    try:
        pros = db.query(ProPlayer).filter(
            ProPlayer.riot_puuid != None,
            ProPlayer.is_active == True
        ).all()

        logger.info(f"🎮 Poll: vérification de {len(pros)} pros...")

        puuids_in_game = set()
        processed_game_ids = set()

        for pro in pros:
            try:
                live = await get_live_game_by_puuid(pro.riot_puuid, pro.region)
                if live:
                    riot_game_id = str(live.get("gameId"))
                    puuids_in_game.add(pro.riot_puuid)

                    if riot_game_id in processed_game_ids:
                        continue
                    processed_game_ids.add(riot_game_id)

                    participants = live.get("participants", [])
                    if participants:
                        logger.info(f"   🔎 Sample participant: {participants[0]}")
                    puuid_to_participant = {p.get("puuid"): p for p in participants}

                    existing = db.query(LiveGame).filter(
                        LiveGame.riot_game_id == riot_game_id
                    ).first()

                    if not existing:
                        try:
                            blue_team = [build_participant(p) for p in participants if p.get("teamId") == 100]
                            red_team  = [build_participant(p) for p in participants if p.get("teamId") == 200]
                            game = LiveGame(
                                searched_player_id=1,
                                riot_game_id=riot_game_id,
                                queue_type=str(live.get("gameQueueConfigId", "")),
                                blue_team=blue_team,
                                red_team=red_team,
                                duration_seconds=live.get("gameLength", 0),
                                status="live",
                            )
                            db.add(game)
                            db.flush()  # détecte le doublon immédiatement
                            logger.info(f"   ✅ Nouvelle partie: {pro.name} ({riot_game_id})")
                        except Exception:
                            db.rollback()
                            logger.warning(f"   ⚠️ Game {riot_game_id} déjà insérée, skip")

                    else:
                        existing.duration_seconds = live.get("gameLength", 0)
                        if existing.status == "ended":
                            existing.status = "live"

                        # Patch noms + spells vides à chaque poll
                        needs_update = any(
                            not p.get("summonerName") or p.get("spell1Id") is None
                            for p in (existing.blue_team or []) + (existing.red_team or [])
                        )
                        if needs_update:
                            existing.blue_team = [
                                {
                                    **p,
                                    "summonerName": extract_summoner_name(
                                        puuid_to_participant.get(p.get("puuid"), p)
                                    ) or p.get("summonerName", ""),
                                    "spell1Id": puuid_to_participant.get(p.get("puuid"), {}).get("spell1Id") or p.get("spell1Id"),
                                    "spell2Id": puuid_to_participant.get(p.get("puuid"), {}).get("spell2Id") or p.get("spell2Id"),
                                }
                                for p in (existing.blue_team or [])
                            ]
                            existing.red_team = [
                                {
                                    **p,
                                    "summonerName": extract_summoner_name(
                                        puuid_to_participant.get(p.get("puuid"), p)
                                    ) or p.get("summonerName", ""),
                                    "spell1Id": puuid_to_participant.get(p.get("puuid"), {}).get("spell1Id") or p.get("spell1Id"),
                                    "spell2Id": puuid_to_participant.get(p.get("puuid"), {}).get("spell2Id") or p.get("spell2Id"),
                                }
                                for p in (existing.red_team or [])
                            ]
                            flag_modified(existing, "blue_team")
                            flag_modified(existing, "red_team")
                            logger.info(f"   🔄 Noms + spells mis à jour pour game {riot_game_id}")

                await asyncio.sleep(1.5)

            except Exception as e:
                logger.error(f"   ❌ Erreur pour {pro.name}: {e}")
                continue

        active_games = db.query(LiveGame).filter(LiveGame.status == "live").all()
        games_to_resolve = []

        for game in active_games:
            still_live = game.riot_game_id in processed_game_ids

            if not still_live:
                game.status = "ended"
                logger.info(f"   🏁 Game {game.riot_game_id} marquée ENDED")

                has_pending = db.query(Bet).filter(
                    Bet.live_game_id == game.id,
                    Bet.status == "pending"
                ).first()

                if has_pending:
                    all_puuids = [
                        p.get("puuid") for p in (game.blue_team or []) + (game.red_team or [])
                        if p.get("puuid")
                    ]
                    pro = db.query(ProPlayer).filter(
                        ProPlayer.riot_puuid.in_(all_puuids)
                    ).first()
                    region = pro.region if pro else ("KR" if "KR" in (game.riot_game_id or "") else "EUW")
                    games_to_resolve.append((game.id, game.riot_game_id, region))

        db.commit()

        for game_id, riot_game_id, region in games_to_resolve:
            logger.info(f"   🎯 Résolution background lancée pour game {game_id}")
            asyncio.create_task(resolve_bets_for_game(game_id, riot_game_id, region))

        logger.info(f"✅ Poll terminé — {len(puuids_in_game)} pros en game")

    except Exception as e:
        logger.error(f"❌ Erreur poll global: {e}")
        db.rollback()
    finally:
        db.close()