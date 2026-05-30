from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db
from deps import get_current_user
from models.user import User
from models.user_card import UserCard
from models.card import Card
from models.transaction import Transaction
from services.lootbox_service import RESALE_PRICES

router = APIRouter(prefix="/cards", tags=["cards"])

# ─── Constantes ────────────────────────────────────────────
MAX_EQUIPPED_STICKERS = 3


# ─── Schemas ───────────────────────────────────────────────
class EquipStickerSchema(BaseModel):
    user_card_id: int
    position_x:   float   # 0-100
    position_y:   float   # 0-100


class MoveStickerSchema(BaseModel):
    user_card_id: int
    position_x:   float
    position_y:   float
    size:         str | None = None


def _clamp(v: float) -> float:
    return max(0.0, min(100.0, v))


# ═══════════════════════════════════════════════════════════
# GET /cards/my-cards
# ═══════════════════════════════════════════════════════════
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
            "id":          uc.id,
            "equipped":    uc.equipped,
            "quantity":    uc.quantity,
            "obtained_at": uc.obtained_at,
            "position_x":  float(uc.position_x) if uc.position_x is not None else None,
            "position_y":  float(uc.position_y) if uc.position_y is not None else None,
            "card": {
                "id":            uc.card.id,
                "name":          uc.card.name,
                "type":          uc.card.type,
                "rarity":        uc.card.rarity,
                "image_url":     uc.card.image_url,
                "boost_type":    uc.card.boost_type,
                "boost_value":   uc.card.boost_value,
                "trigger_type":  uc.card.trigger_type,
                "trigger_value": uc.card.trigger_value,
                "is_banner":     uc.card.is_banner,
                "is_title":      uc.card.is_title,
                "title_text":    uc.card.title_text,
                "collection":    uc.card.collection,
                "artist":        uc.card.artist,
                "lore":          uc.card.lore,
            },
        }
        for uc in user_cards
    ]


# ═══════════════════════════════════════════════════════════
# POST /cards/{user_card_id}/sell
# ═══════════════════════════════════════════════════════════
@router.post("/{user_card_id}/sell")
def sell_card(
    user_card_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    uc = (
        db.query(UserCard)
        .filter(UserCard.id == user_card_id, UserCard.user_id == current_user.id)
        .with_for_update()
        .first()
    )
    if not uc:
        raise HTTPException(404, "Carte introuvable dans ton inventaire")

    price = RESALE_PRICES.get(uc.card.rarity)
    if price is None:
        raise HTTPException(400, f"Rareté inconnue: {uc.card.rarity}")

    # Auto-unequip si dernière copie
    if uc.quantity <= 1:
        uc.equipped   = False
        uc.position_x = None
        uc.position_y = None

    user = (
        db.query(User)
        .filter(User.id == current_user.id)
        .with_for_update()
        .first()
    )
    user.coins += price

    db.add(Transaction(
        user_id=user.id,
        type="card_sold",
        amount=price,
        description=f"Revente carte: {uc.card.name} ({uc.card.rarity})",
    ))

    remaining = uc.quantity - 1
    if remaining > 0:
        uc.quantity = remaining
    else:
        db.delete(uc)

    db.commit()

    return {
        "success":            True,
        "coins_gained":       price,
        "coins_total":        user.coins,
        "remaining_quantity": remaining,
    }


# ═══════════════════════════════════════════════════════════
# GET /cards/collection-progress
# ═══════════════════════════════════════════════════════════
@router.get("/collection-progress")
def collection_progress(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Renvoie toutes les cartes du jeu groupées par (type, collection),
    avec owned + quantity + user_card_id pour chaque.
    """
    all_cards = (
        db.query(Card)
        .order_by(Card.type, Card.collection.nullsfirst(), Card.rarity, Card.name)
        .all()
    )

    user_cards = (
        db.query(UserCard)
        .filter(UserCard.user_id == current_user.id)
        .all()
    )
    uc_by_card = {uc.card_id: uc for uc in user_cards}

    groups = {}
    for c in all_cards:
        uc = uc_by_card.get(c.id)
        entry = {
            "card": {
                "id":            c.id,
                "name":          c.name,
                "type":          c.type,
                "rarity":        c.rarity,
                "image_url":     c.image_url,
                "boost_type":    c.boost_type,
                "boost_value":   c.boost_value,
                "trigger_type":  c.trigger_type,
                "trigger_value": c.trigger_value,
                "is_banner":     c.is_banner,
                "is_title":      c.is_title,
                "title_text":    c.title_text,
                "collection":    c.collection,
                "artist":        c.artist,
                "lore":          c.lore,
            },
            "owned":        uc is not None,
            "quantity":     uc.quantity if uc else 0,
            "user_card_id": uc.id if uc else None,
            "equipped":     uc.equipped if uc else False,
        }
        groups.setdefault(c.type, {}).setdefault(c.collection or "__none__", []).append(entry)

    result = {}
    for type_key, by_coll in groups.items():
        collections = []
        for coll_name, entries in by_coll.items():
            owned_count = sum(1 for e in entries if e["owned"])
            collections.append({
                "name":  None if coll_name == "__none__" else coll_name,
                "total": len(entries),
                "owned": owned_count,
                "cards": entries,
            })
        collections.sort(key=lambda c: (c["name"] is None, c["name"] or ""))
        result[type_key] = collections

    return result


# ═══════════════════════════════════════════════════════════
# STICKERS — positions libres x/y (en %)
# ═══════════════════════════════════════════════════════════

# ─── POST /cards/equip-sticker ─────────────────────────────
@router.post("/equip-sticker")
def equip_sticker(
    body: EquipStickerSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    uc = (
        db.query(UserCard)
        .filter(UserCard.id == body.user_card_id, UserCard.user_id == current_user.id)
        .first()
    )
    if not uc:
        raise HTTPException(404, "Carte introuvable")
    if uc.card.type != "sticker":
        raise HTTPException(400, "Seuls les stickers peuvent être équipés sur la bannière")

    if not uc.equipped:
        equipped_count = (
            db.query(UserCard)
            .filter(UserCard.user_id == current_user.id, UserCard.equipped == True)
            .count()
        )
        if equipped_count >= MAX_EQUIPPED_STICKERS:
            raise HTTPException(400, f"Maximum {MAX_EQUIPPED_STICKERS} stickers équipés")
        uc.equipped = True

    uc.position_x = _clamp(body.position_x)
    uc.position_y = _clamp(body.position_y)
    db.commit()

    return {
        "success":      True,
        "user_card_id": uc.id,
        "position_x":   float(uc.position_x),
        "position_y":   float(uc.position_y),
    }


# ─── POST /cards/move-sticker ──────────────────────────────
@router.post("/move-sticker")
def move_sticker(
    body: MoveStickerSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Met à jour la position d'un sticker déjà équipé (drag)."""
    uc = (
        db.query(UserCard)
        .filter(
            UserCard.id == body.user_card_id,
            UserCard.user_id == current_user.id,
            UserCard.equipped == True,
        )
        .first()
    )
    if not uc:
        raise HTTPException(404, "Sticker équipé introuvable")

    uc.position_x = _clamp(body.position_x)
    uc.position_y = _clamp(body.position_y)
    if body.size in ("small", "medium", "large"):
        uc.size = body.size
    db.commit()

    return {
        "success":    True,
        "position_x": float(uc.position_x),
        "position_y": float(uc.position_y),
        "size":       uc.size,
    }


# ─── DELETE /cards/equip-sticker/{user_card_id} ────────────
@router.delete("/equip-sticker/{user_card_id}")
def unequip_sticker(
    user_card_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    uc = (
        db.query(UserCard)
        .filter(
            UserCard.id == user_card_id,
            UserCard.user_id == current_user.id,
            UserCard.equipped == True,
        )
        .first()
    )
    if not uc:
        raise HTTPException(404, "Sticker équipé introuvable")

    uc.equipped   = False
    uc.position_x = None
    uc.position_y = None
    uc.size = None
    db.commit()
    return {"success": True}


# ─── GET /cards/equipped-stickers ──────────────────────────
@router.get("/equipped-stickers")
def get_equipped_stickers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _equipped_stickers_for(db, current_user.id)

# ─── GET /cards/equipped-stickers/public/{user_id} ──────────
@router.get("/equipped-stickers/public/{user_id}")
def get_equipped_stickers_public(
    user_id: int,
    db: Session = Depends(get_db),
):
    return _equipped_stickers_for(db, user_id)
    
def _equipped_stickers_for(db: Session, user_id: int) -> list:
    """Helper réutilisable (utilisable depuis profile/user routers)."""
    rows = (
        db.query(UserCard)
        .filter(UserCard.user_id == user_id, UserCard.equipped == True)
        .all()
    )
    out = []
    for uc in rows:
        if uc.card.type != "sticker":
            continue
        out.append({
            "user_card_id": uc.id,
            "position_x":   float(uc.position_x) if uc.position_x is not None else 50.0,
            "position_y":   float(uc.position_y) if uc.position_y is not None else 50.0,
            "size":         uc.size or "medium",
            "card": {
                "id":        uc.card.id,
                "name":      uc.card.name,
                "rarity":    uc.card.rarity,
                "image_url": uc.card.image_url,
                "type":      uc.card.type,
                "collection": uc.card.collection,
                "artist":    uc.card.artist,
                "lore":      uc.card.lore,
            },
        })
    return out

# ═══════════════════════════════════════════════════════════
# TITRES — équipe / déséquipe (POST + DELETE /equip-title)
# ═══════════════════════════════════════════════════════════

class EquipTitleSchema(BaseModel):
    user_card_id: int

@router.post("/equip-title")
def equip_title(
    body: EquipTitleSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    uc = (
        db.query(UserCard)
        .filter(UserCard.id == body.user_card_id, UserCard.user_id == current_user.id)
        .first()
    )
    if not uc:
        raise HTTPException(404, "Carte introuvable dans ton inventaire")
    if not uc.card.is_title:
        raise HTTPException(400, "Cette carte n'est pas un titre")

    current_user.equipped_title_id = uc.card.id
    db.commit()

    return {
        "success":           True,
        "equipped_title_id": uc.card.id,
        "title_text":        uc.card.title_text,
    }


@router.delete("/equip-title")
def unequip_title(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.equipped_title_id = None
    db.commit()
    return {"success": True}