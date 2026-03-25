from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models.bet import Bet
from models.live_game import LiveGame
from models.user import User
from models.bet_type import BetType
from deps import get_current_user
from datetime import datetime

router = APIRouter(prefix="/bets", tags=["bets"])


class PlaceBetSchema(BaseModel):
    live_game_id: int
    bet_type_slug: str
    bet_value: str
    amount: int
    card_used_id: int | None = None


@router.post("/place")
def place_bet(
    body: PlaceBetSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bet_type = db.query(BetType).filter(
        BetType.slug == body.bet_type_slug,
        BetType.is_active == True,
    ).first()
    if not bet_type:
        raise HTTPException(400, "Type de pari invalide ou inactif")

    game = db.query(LiveGame).filter(
        LiveGame.id == body.live_game_id,
        LiveGame.status == "live",
    ).first()
    if not game:
        raise HTTPException(400, "Partie introuvable ou déjà terminée")

    existing = db.query(Bet).filter(
        Bet.user_id == current_user.id,
        Bet.live_game_id == body.live_game_id,
        Bet.bet_type_slug == body.bet_type_slug,
    ).first()
    if existing:
        raise HTTPException(400, "Tu as déjà placé ce type de pari sur cette partie")

    if current_user.coins < body.amount:
        raise HTTPException(400, f"Pas assez de coins ({current_user.coins} disponibles, {body.amount} requis)")

    boost = 0.0
    if body.card_used_id:
        from models.card import Card
        from models.user_card import UserCard
        user_card = db.query(UserCard).filter(
            UserCard.user_id == current_user.id,
            UserCard.card_id == body.card_used_id,
        ).first()
        if not user_card:
            raise HTTPException(400, "Tu ne possèdes pas cette carte")
        boost = user_card.card.boost_value or 0.0

    current_user.coins -= body.amount

    bet = Bet(
        user_id=current_user.id,
        live_game_id=body.live_game_id,
        card_used_id=body.card_used_id,
        bet_type_slug=body.bet_type_slug,
        bet_value=body.bet_value,
        amount=body.amount,
        boost_applied=boost,
        status="pending",
    )
    db.add(bet)

    from models.transaction import Transaction
    transaction = Transaction(
        user_id=current_user.id,
        type="bet_placed",
        amount=-body.amount,
        description=f"Pari placé sur {bet_type.label}",
    )
    db.add(transaction)
    db.commit()
    db.refresh(bet)

    return {
        "bet_id": bet.id,
        "amount": body.amount,
        "boost_applied": boost,
        "coins_restants": current_user.coins,
    }


@router.get("/my-bets")
def get_my_bets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bets = (
        db.query(Bet)
        .filter(Bet.user_id == current_user.id)
        .order_by(Bet.created_at.desc())
        .all()
    )
    return [
        {
            "id": b.id,
            "bet_type": b.bet_type_slug,
            "bet_value": b.bet_value,
            "amount": b.amount,
            "boost_applied": b.boost_applied,
            "status": b.status,
            "payout": b.payout,
            "created_at": b.created_at,
        }
        for b in bets
    ]

class SelectionSchema(BaseModel):
    type: str   # "who_wins" | "first_blood"
    value: str  # "blue" | "red" | "Renekton"

class PlaceBetSchema(BaseModel):
    live_game_id: int
    selections: list[SelectionSchema]  # le combiné
    amount: int
    card_used_id: int | None = None

@router.post("/place")
def place_bet(
    body: PlaceBetSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    game = db.query(LiveGame).filter(
        LiveGame.id == body.live_game_id,
        LiveGame.status == "live"
    ).first()
    if not game:
        raise HTTPException(400, "Partie introuvable ou terminée")

    # Clôture 5 min
    if game.duration_seconds >= 300:
        raise HTTPException(400, "Paris fermés — la partie a dépassé 5 minutes")

    # Un seul pari par game par user
    existing = db.query(Bet).filter(
        Bet.user_id == current_user.id,
        Bet.live_game_id == body.live_game_id,
    ).first()
    if existing:
        raise HTTPException(400, "Tu as déjà parié sur cette partie")

    if current_user.coins < body.amount:
        raise HTTPException(400, f"Pas assez de coins ({current_user.coins} disponibles)")

    if not body.selections:
        raise HTTPException(400, "Aucune sélection")

    # Cote totale : x2 par sélection
    odds = 2.0 ** len(body.selections)

    # Déduire les coins
    current_user.coins -= body.amount

    bet = Bet(
        user_id=current_user.id,
        live_game_id=body.live_game_id,
        bet_type_slug="combined",
        bet_value=json.dumps({
            "selections": [s.dict() for s in body.selections]
        }),
        amount=body.amount,
        odds=odds,
        boost_applied=0.0,
        status="pending",
        payout=0,
    )
    db.add(bet)

    transaction = Transaction(
        user_id=current_user.id,
        type="bet_placed",
        amount=-body.amount,
        description=f"Pari combiné ({len(body.selections)} sélections) · cote x{odds:.1f}"
    )
    db.add(transaction)
    db.commit()
    db.refresh(bet)

    return {
        "success": True,
        "bet_id": bet.id,
        "odds": odds,
        "potential_gain": int(body.amount * odds),
        "new_balance": current_user.coins,
    }