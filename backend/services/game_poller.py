import asyncio
import json
import logging
from sqlalchemy.orm import Session
from database import SessionLocal
from models.pro_player import ProPlayer
from models.live_game import LiveGame
from models.bet import Bet
from models.transaction import Transaction
from models.user import User
from services.riot import get_live_game_by_puuid, get_match_result_by_game_id

logger = logging.getLogger(__name__)


async def resolve_bets(db: Session, game: LiveGame):
    try:
        result = await get_match_result_by_game_id(game.riot_game_id, game)
        if not result:
            logger.warning(f"   ⚠️ Résultat introuvable pour {game.riot_game_id} — paris marqués lost par défaut")
            bets = db.query(Bet).filter(Bet.live_game_id == game.id, Bet.status == "pending").all()
            for bet in bets:
                bet.status = "lost"
            db.commit()
            return

        winner = result["winner"]
        first_blood_champ = result["first_blood_champion"]
        logger.info(f"   📊 Résultat — winner: {winner}, first_blood: {first_blood_champ}")

        bets = db.query(Bet).filter(
            Bet.live_game_id == game.id,
            Bet.status == "pending"
        ).all()

        for bet in bets:
            try:
                data = json.loads(bet.bet_value)
                selections = data.get("selections", [])

                won = True
                for sel in selections:
                    if sel["type"] == "who_wins":
                        if sel["value"] != winner:
                            won = False
                            break
                    elif sel["type"] == "first_blood":
                        if sel["value"] != first_blood_champ:
                            won = False
                            break

                user = db.query(User).filter(User.id == bet.user_id).first()

                if won:
                    payout = int(bet.amount * (bet.odds or 2.0))
                    bet.status = "won"
                    bet.payout = payout
                    if user:
                        user.coins += payout
                    db.add(Transaction(
                        user_id=bet.user_id,
                        type="bet_won",
                        amount=payout,
                        description=f"Pari gagné · x{bet.odds:.1f} · {payout} coins"
                    ))
                    logger.info(f"   ✅ Pari {bet.id} gagné — {payout} coins crédités à user {bet.user_id}")
                else:
                    bet.status = "lost"
                    bet.payout = 0
                    db.add(Transaction(
                        user_id=bet.user_id,
                        type="bet_lost",
                        amount=0,
                        description="Pari perdu"
                    ))
                    logger.info(f"   ❌ Pari {bet.id} perdu — user {bet.user_id}")

            except Exception as e:
                logger.error(f"   ❌ Erreur résolution pari {bet.id}: {e}")
                continue

        db.commit()

    except Exception as e:
        logger.error(f"   ❌ Erreur resolve_bets pour game {game.riot_game_id}: {e}")


async def poll_pro_games():
    db: Session = SessionLocal()
    try:
        pros = db.query(ProPlayer).filter(
            ProPlayer.riot_puuid != None,
            ProPlayer.is_active == True,
            ProPlayer.region.in_(["KR", "EUW"])
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
                        logger.info(f"   ⏭️ {riot_game_id} déjà traité ce poll")
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
                        logger.info(f"   ✅ Nouvelle partie détectée pour {pro.name} ({pro.team})")
                    else:
                        existing.duration_seconds = live.get("gameLength", 0)
                        if existing.status == "ended":
                            existing.status = "live"

                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"   ❌ Erreur pour {pro.name}: {e}")
                continue

        db.commit()

        # Résoudre les parties terminées
        active_games = db.query(LiveGame).filter(LiveGame.status == "live").all()
        for game in active_games:
            all_puuids = [p.get("puuid") for p in game.blue_team + game.red_team]
            still_live = any(puuid in puuids_in_game for puuid in all_puuids if puuid)

            if not still_live:
                logger.info(f"   🏁 Partie {game.riot_game_id} terminée — résolution des paris...")
                await resolve_bets(db, game)
                db.delete(game)
                logger.info(f"   🗑️ Partie {game.riot_game_id} supprimée")

        db.commit()
        logger.info(f"✅ Poll terminé — {len(puuids_in_game)} pros en game")

    except Exception as e:
        logger.error(f"❌ Erreur poll global: {e}")
        db.rollback()
    finally:
        db.close()