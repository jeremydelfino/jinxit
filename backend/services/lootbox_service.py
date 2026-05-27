"""
Service de tirage de carte depuis une caisse.
Algo : tirage rareté pondéré → filtrage pool de cartes → tirage uniforme.
"""
import random
from sqlalchemy.orm import Session
from sqlalchemy import text
from models.card import Card
from models.lootbox import LootBoxType
from models.user_card import UserCard

# Prix de revente par rareté (en coins)
RESALE_PRICES = {
    "common":    50,
    "rare":      200,
    "epic":      800,
    "legendary": 3000,
}


def pick_card_from_box(db: Session, box_type: LootBoxType) -> Card | None:
    """
    Tire une carte au hasard selon les drop rates de la caisse,
    en filtrant sur les types autorisés (box_type.pool_types CSV).
    Retourne None si la pool est vide pour TOUS les types.
    """
    # 1. Tirage de la rareté
    weights = [
        ("common",    box_type.drop_common),
        ("rare",      box_type.drop_rare),
        ("epic",      box_type.drop_epic),
        ("legendary", box_type.drop_legendary),
    ]
    rarities, w = zip(*weights)
    chosen_rarity = random.choices(rarities, weights=w, k=1)[0]

    # 2. Types autorisés
    allowed_types = [t.strip() for t in box_type.pool_types.split(",") if t.strip()]
    if not allowed_types:
        return None

# 3. Pool de cartes correspondant
    query = db.query(Card).filter(Card.rarity == chosen_rarity, Card.type.in_(allowed_types))

    # Filtre collection si défini
    if box_type.collection_filter:
        allowed_collections = [c.strip() for c in box_type.collection_filter.split(",") if c.strip()]
        if allowed_collections:
            query = query.filter(Card.collection.in_(allowed_collections))

    candidates = query.all()

    # Fallback : si rien à cette rareté, on essaie les autres
    if not candidates:
        fallback_order = ["legendary", "epic", "rare", "common"]
        for fb in fallback_order:
            if fb == chosen_rarity:
                continue
            fb_query = db.query(Card).filter(Card.rarity == fb, Card.type.in_(allowed_types))
            if box_type.collection_filter:
                allowed_collections = [c.strip() for c in box_type.collection_filter.split(",") if c.strip()]
                if allowed_collections:
                    fb_query = fb_query.filter(Card.collection.in_(allowed_collections))
            candidates = fb_query.all()
            if candidates:
                break

    if not candidates:
        return None
    return random.choice(candidates)


def grant_card_to_user(db: Session, user_id: int, card_id: int) -> None:
    """
    Ajoute la carte à l'inventaire. Si déjà possédée → quantity += 1.
    Utilise ON CONFLICT pour atomicité.
    """
    db.execute(
        text("""
            INSERT INTO user_cards (user_id, card_id, quantity, equipped)
            VALUES (:uid, :cid, 1, false)
            ON CONFLICT (user_id, card_id)
            DO UPDATE SET quantity = user_cards.quantity + 1
        """),
        {"uid": user_id, "cid": card_id},
    )