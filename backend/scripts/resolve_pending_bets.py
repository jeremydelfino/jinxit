"""
Script de résolution manuelle des paris pending.
Lance depuis le dossier backend/ : python scripts/resolve_pending_bets.py
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ✅ Importer TOUS les modèles pour que SQLAlchemy resolve les FK correctement
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

import asyncio
from database import SessionLocal
from models.live_game import LiveGame
from models.bet import Bet
from models.user import User
from models.transaction import Transaction
from models.pro_player import ProPlayer
from services.riot import get_match_result


async def resolve_game(db, game_id: int):
    game = db.query(LiveGame).filter(LiveGame.id == game_id).first()
    if not game:
        print(f"❌ Game {game_id} introuvable")
        return

    print(f"\n🎮 Game {game_id} — riot_id: {game.riot_game_id} — status: {game.status}")

    all_p  = (game.blue_team or []) + (game.red_team or [])
    puuids = [p.get("puuid") for p in all_p if p.get("puuid")]
    pro    = db.query(ProPlayer).filter(ProPlayer.riot_puuid.in_(puuids)).first()
    region = pro.region if pro else "EUW"
    ref_puuid = puuids[0] if puuids else None

    print(f"   Region: {region}, ref_puuid: {ref_puuid[:20] if ref_puuid else 'None'}...")

    if not ref_puuid:
        print(f"   ❌ Pas de puuid de référence")
        return

    print(f"   🔍 Récupération résultat MATCH-V5...")
    result = await get_match_result(ref_puuid, game.riot_game_id, region)

    if not result:
        print(f"   ❌ Résultat MATCH-V5 indisponible — annulation et remboursement")
        pending = db.query(Bet).filter(Bet.live_game_id == game_id, Bet.status == "pending").all()
        for bet in pending:
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
            print(f"   ↩️  Bet {bet.id} annulé, {bet.amount} coins remboursés à user {bet.user_id}")
        db.commit()
        return

    winner_team = result.get("winner_team")
    first_blood = result.get("first_blood")
    print(f"   🏆 Résultat: winner={winner_team}, first_blood={first_blood}")

    pending = db.query(Bet).filter(Bet.live_game_id == game_id, Bet.status == "pending").all()
    if not pending:
        print(f"   ℹ️  Aucun pari pending")
        return

    for bet in pending:
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
            print(f"   ↩️  Bet {bet.id} annulé (type inconnu)")
            continue

        if won:
            multiplier = 2.0 * (1 + (bet.boost_applied or 0) / 100)
            payout     = int(bet.amount * multiplier)
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
            print(f"   ✅ Bet {bet.id} GAGNÉ → +{payout} coins (user {bet.user_id})")
        else:
            bet.status = "lost"
            bet.payout = 0
            print(f"   ❌ Bet {bet.id} PERDU (user {bet.user_id}, misait sur {bet.bet_value}, gagnant={winner_team})")

    db.commit()
    print(f"   ✅ Commit OK — résolution terminée pour game {game_id}")


async def main():
    db = SessionLocal()
    try:
        await resolve_game(db, 33)
        await resolve_game(db, 35)
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())