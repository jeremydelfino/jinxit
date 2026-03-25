from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models.user import User
from models.user_card import UserCard
from models.card import Card
from deps import get_current_user

router = APIRouter(prefix="/cards", tags=["cards"])


@router.get("/my-cards")
def get_my_cards(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_cards = (
        db.query(UserCard)
        .filter(UserCard.user_id == current_user.id)
        .join(Card, UserCard.card_id == Card.id)
        .order_by(Card.rarity.desc(), Card.name)
        .all()
    )

    return [
        {
            "id": uc.id,
            "equipped": uc.equipped,
            "obtained_at": uc.obtained_at,
            "card": {
                "id": uc.card.id,
                "name": uc.card.name,
                "type": uc.card.type,
                "rarity": uc.card.rarity,
                "image_url": uc.card.image_url,
                "boost_type": uc.card.boost_type,
                "boost_value": uc.card.boost_value,
                "trigger_type": uc.card.trigger_type,
                "trigger_value": uc.card.trigger_value,
                "is_banner": uc.card.is_banner,
                "is_title": uc.card.is_title,
                "title_text": uc.card.title_text,
            }
        }
        for uc in user_cards
    ]