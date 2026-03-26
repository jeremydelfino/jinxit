import asyncio
import logging

# ✅ Importer tous les modèles pour que SQLAlchemy resolve les FK au commit
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

from sqlalchemy.orm import Session
from database import SessionLocal
from models.pro_player import ProPlayer
from models.live_game import LiveGame
from models.bet import Bet
from models.user import User
from models.transaction import Transaction
from services.riot import get_live_game_by_puuid, get_match_result

logger = logging.getLogger(__name__)


async def resolve_bets_for_game(game_id: int, riot_game_id: str, region: str):
    """
    Résout les paris pending d'une game terminée.
    Appelé en background — retry MATCH-V5 jusqu'à 5 fois (1 min entre chaque).
    """
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

        # Retry jusqu'à 5 fois — MATCH-V5 peut prendre quelques minutes
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
            # Rembourser si MATCH-V5 indisponible après 5 tentatives
            logger.error(f"   ❌ MATCH-V5 indisponible après 5 tentatives — remboursement")
            for bet in pending_bets:
                bet.status = "cancelled"
                user = db.query(User).filter(User.id == bet.user_id).first()
                if user:
                    user.coins += bet.amount
                    db.add(Transaction(
                        user_id=user.id,
                        type="bet_placed",
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
                won = first_blood and bet.bet_value.lower() == first_blood.lower()
            else:
                bet.status = "cancelled"
                user = db.query(User).filter(User.id == bet.user_id).first()
                if user:
                    user.coins += bet.amount
                continue

            if won:
                multiplier = 2.0 * (1 + (bet.boost_applied or 0) / 100)
                payout = int(bet.amount * multiplier)
                bet.status = "won"
                bet.payout = payout
                user = db.query(User).filter(User.id == bet.user_id).first()
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
        ).limit(20).all()

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

                    existing = db.query(LiveGame).filter(
                        LiveGame.riot_game_id == riot_game_id
                    ).first()

                    if not existing:
                        participants = live.get("participants", [])
                        blue_team = [
                            {
                                "puuid":        p.get("puuid", ""),
                                "summonerName": p.get("summonerName", ""),
                                "championId":   p.get("championId"),
                                "championName": p.get("championName", ""),
                                "teamId":       p.get("teamId"),
                            }
                            for p in participants if p.get("teamId") == 100
                        ]
                        red_team = [
                            {
                                "puuid":        p.get("puuid", ""),
                                "summonerName": p.get("summonerName", ""),
                                "championId":   p.get("championId"),
                                "championName": p.get("championName", ""),
                                "teamId":       p.get("teamId"),
                            }
                            for p in participants if p.get("teamId") == 200
                        ]
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
                        logger.info(f"   ✅ Nouvelle partie: {pro.name} ({riot_game_id})")
                    else:
                        existing.duration_seconds = live.get("gameLength", 0)
                        if existing.status == "ended":
                            existing.status = "live"

                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"   ❌ Erreur pour {pro.name}: {e}")
                continue

        # Détecter les games terminées
        active_games = db.query(LiveGame).filter(LiveGame.status == "live").all()
        games_to_resolve = []

        for game in active_games:
            all_puuids = [
                p.get("puuid") for p in (game.blue_team or []) + (game.red_team or [])
                if p.get("puuid")
            ]
            still_live = any(puuid in puuids_in_game for puuid in all_puuids)

            if not still_live:
                # ✅ Marquer ended — NE JAMAIS supprimer (les paris y sont liés par FK)
                game.status = "ended"
                logger.info(f"   🏁 Game {game.riot_game_id} marquée ENDED")

                has_pending = db.query(Bet).filter(
                    Bet.live_game_id == game.id,
                    Bet.status == "pending"
                ).first()

                if has_pending:
                    pro = db.query(ProPlayer).filter(
                        ProPlayer.riot_puuid.in_(all_puuids)
                    ).first()
                    region = pro.region if pro else "EUW"
                    games_to_resolve.append((game.id, game.riot_game_id, region))

        db.commit()

        # ✅ Résolution en background — ne bloque pas le poller
        for game_id, riot_game_id, region in games_to_resolve:
            logger.info(f"   🎯 Résolution background lancée pour game {game_id}")
            asyncio.create_task(resolve_bets_for_game(game_id, riot_game_id, region))

        logger.info(f"✅ Poll terminé — {len(puuids_in_game)} pros en game")

    except Exception as e:
        logger.error(f"❌ Erreur poll global: {e}")
        db.rollback()
    finally:
        db.close()