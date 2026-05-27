from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel
from typing import Optional

from database import get_db
from deps import get_current_user
from models.user import User
from models.lootbox import LootBox, LootBoxType
from services.lootbox_service import pick_card_from_box, grant_card_to_user

router = APIRouter(prefix="/lootbox", tags=["lootbox"])


# ─── GET /lootbox/my-boxes ─────────────────────────────────
@router.get("/my-boxes")
def my_boxes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Caisses non ouvertes de l'user."""
    boxes = (
        db.query(LootBox)
        .filter(LootBox.user_id == current_user.id, LootBox.opened_at.is_(None))
        .order_by(LootBox.obtained_at.desc())
        .all()
    )
    return [
        {
            "id": b.id,
            "obtained_at": b.obtained_at,
            "box_type": {
                "id":          b.box_type.id,
                "name":        b.box_type.name,
                "description": b.box_type.description,
                "image_url":   b.box_type.image_url,
                "drop_rates": {
                    "common":    b.box_type.drop_common,
                    "rare":      b.box_type.drop_rare,
                    "epic":      b.box_type.drop_epic,
                    "legendary": b.box_type.drop_legendary,
                },
                "collection_filter": t.collection_filter,
            },
        }
        for b in boxes
    ]


# ─── GET /lootbox/types (catalogue achetable) ──────────────
@router.get("/types")
def list_box_types(db: Session = Depends(get_db)):
    """Liste des types de caisses actifs (pour shop)."""
    types = (
        db.query(LootBoxType)
        .filter(LootBoxType.is_active == True)
        .order_by(LootBoxType.price_coins.asc().nulls_last())
        .all()
    )
    return [
        {
            "id":          t.id,
            "name":        t.name,
            "description": t.description,
            "image_url":   t.image_url,
            "price_coins": t.price_coins,
            "pool_types":  t.pool_types,
            "drop_rates": {
                "common":    t.drop_common,
                "rare":      t.drop_rare,
                "epic":      t.drop_epic,
                "legendary": t.drop_legendary,
            },
            "collection_filter": t.collection_filter,
        }
        for t in types
    ]


# ─── POST /lootbox/{box_id}/open ───────────────────────────
@router.post("/{box_id}/open")
def open_box(
    box_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    box = (
        db.query(LootBox)
        .filter(LootBox.id == box_id, LootBox.user_id == current_user.id)
        .first()
    )
    if not box:
        raise HTTPException(404, "Caisse introuvable")
    if box.opened_at is not None:
        raise HTTPException(400, "Caisse déjà ouverte")

    card = pick_card_from_box(db, box.box_type)
    if not card:
        raise HTTPException(500, "Pool de cartes vide pour cette caisse")

    grant_card_to_user(db, current_user.id, card.id)

    box.opened_at = datetime.utcnow()
    box.opened_card_id = card.id
    db.commit()

    return {
        "success": True,
        "card": {
            "id":         card.id,
            "name":       card.name,
            "type":       card.type,
            "rarity":     card.rarity,
            "image_url":  card.image_url,
        },
    }


# ─── ADMIN — Création/édition des types de caisses ─────────
# (gating is_admin pas encore brancché ici — à toi de voir si tu veux
#  réutiliser la même mécanique que ton AdminRatings/AdminCards)

class CreateBoxTypeSchema(BaseModel):
    name:              str
    description:       Optional[str] = None
    image_url:         Optional[str] = None
    price_coins:       Optional[int] = None
    pool_types:        str
    collection_filter: Optional[str] = None
    drop_common:    int = 60
    drop_rare:      int = 25
    drop_epic:      int = 12
    drop_legendary: int = 3


from fastapi import UploadFile, File, Form
from services.cloudinary_service import upload_image

@router.post("/admin/types")
async def admin_create_box_type(
    name:              str           = Form(...),
    description:       Optional[str] = Form(None),
    pool_types:        str           = Form(...),
    collection_filter: Optional[str] = Form(None),
    price_coins:       Optional[int] = Form(None),
    drop_common:       int           = Form(60),
    drop_rare:         int           = Form(25),
    drop_epic:         int           = Form(12),
    drop_legendary:    int           = Form(3),
    file:              Optional[UploadFile] = File(None),
    db:                Session       = Depends(get_db),
    current_user:      User          = Depends(get_current_user),
):
    if not getattr(current_user, "is_admin", False):
        raise HTTPException(403, "Admin uniquement")

    total = drop_common + drop_rare + drop_epic + drop_legendary
    if total != 100:
        raise HTTPException(400, f"Drop rates doivent totaliser 100 (actuel: {total})")

    image_url = None
    if file:
        if file.content_type not in ["image/jpeg", "image/png", "image/webp"]:
            raise HTTPException(400, "Format non supporté (jpeg, png, webp)")
        contents = await file.read()
        safe_name = name.lower().replace(" ", "_").replace("—", "-")
        image_url = await upload_image(contents, folder="junglegap/lootboxes", public_id=f"box_{safe_name}")

    box_type = LootBoxType(
        name=name,
        description=description,
        image_url=image_url,
        price_coins=price_coins,
        pool_types=pool_types,
        collection_filter=collection_filter,
        drop_common=drop_common,
        drop_rare=drop_rare,
        drop_epic=drop_epic,
        drop_legendary=drop_legendary,
    )
    db.add(box_type)
    db.commit()
    db.refresh(box_type)
    return {"success": True, "id": box_type.id, "name": box_type.name, "image_url": image_url}


# ─── POST /lootbox/buy/{box_type_id} ───────────────────────
@router.post("/buy/{box_type_id}")
def buy_box(
    box_type_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Achat d'une caisse contre des coins."""
    box_type = (
        db.query(LootBoxType)
        .filter(LootBoxType.id == box_type_id)
        .first()
    )
    if not box_type:
        raise HTTPException(404, "Type de caisse introuvable")
    if not box_type.is_active:
        raise HTTPException(400, "Cette caisse n'est plus disponible")
    if box_type.price_coins is None:
        raise HTTPException(400, "Cette caisse n'est pas achetable")

    # Lock user pour éviter double-spend
    user = (
        db.query(User)
        .filter(User.id == current_user.id)
        .with_for_update()
        .first()
    )
    if user.coins < box_type.price_coins:
        raise HTTPException(400, f"Coins insuffisants ({user.coins}/{box_type.price_coins})")

    user.coins -= box_type.price_coins
    box = LootBox(user_id=user.id, box_type_id=box_type.id)
    db.add(box)

    from models.transaction import Transaction
    db.add(Transaction(
        user_id=user.id,
        type="lootbox_purchase",
        amount=-box_type.price_coins,
        description=f"Achat caisse: {box_type.name}",
    ))
    db.commit()
    db.refresh(box)

    return {
        "success":         True,
        "lootbox_id":      box.id,
        "coins_remaining": user.coins,
        "box_type": {
            "id":   box_type.id,
            "name": box_type.name,
        },
    }

# ─── ADMIN — Donner une caisse à un user (debug/cadeaux) ───
@router.post("/admin/grant/{user_id}/{box_type_id}")
def admin_grant_box(
    user_id: int,
    box_type_id: int,
    quantity: int = 1,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not getattr(current_user, "is_admin", False):
        raise HTTPException(403, "Admin uniquement")
    box_type = db.query(LootBoxType).filter(LootBoxType.id == box_type_id).first()
    if not box_type:
        raise HTTPException(404, "Type de caisse introuvable")

    for _ in range(quantity):
        db.add(LootBox(user_id=user_id, box_type_id=box_type_id))
    db.commit()
    return {"success": True, "granted": quantity, "to_user_id": user_id}

# ─── ADMIN — GET /lootbox/admin/types (tous, actifs + inactifs) ────
@router.get("/admin/types")
def admin_list_box_types(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not getattr(current_user, "is_admin", False):
        raise HTTPException(403, "Admin uniquement")
    types = db.query(LootBoxType).order_by(LootBoxType.id).all()
    return [
        {
            "id":          t.id,
            "name":        t.name,
            "description": t.description,
            "image_url":   t.image_url,
            "price_coins": t.price_coins,
            "pool_types":  t.pool_types,
            "is_active":   t.is_active,
            "drop_rates": {
                "common":    t.drop_common,
                "rare":      t.drop_rare,
                "epic":      t.drop_epic,
                "legendary": t.drop_legendary,
            },
            "collection_filter": t.collection_filter,
        }
        for t in types
    ]


# ─── ADMIN — PATCH /lootbox/admin/types/{id} ───────────────
class PatchBoxTypeSchema(BaseModel):
    name:           Optional[str]   = None
    description:    Optional[str]   = None
    image_url:      Optional[str]   = None
    price_coins:    Optional[int]   = None
    pool_types:     Optional[str]   = None
    drop_common:    Optional[int]   = None
    drop_rare:      Optional[int]   = None
    drop_epic:      Optional[int]   = None
    drop_legendary: Optional[int]   = None
    is_active:      Optional[bool]  = None
    collection_filter: Optional[str] = None


@router.patch("/admin/types/{box_type_id}")
async def admin_patch_box_type(
    box_type_id: int,
    name:              Optional[str] = Form(None),
    description:       Optional[str] = Form(None),
    pool_types:        Optional[str] = Form(None),
    collection_filter: Optional[str] = Form(None),
    price_coins:       Optional[int] = Form(None),
    drop_common:       Optional[int] = Form(None),
    drop_rare:         Optional[int] = Form(None),
    drop_epic:         Optional[int] = Form(None),
    drop_legendary:    Optional[int] = Form(None),
    is_active:         Optional[bool] = Form(None),
    file:              Optional[UploadFile] = File(None),
    db:                Session       = Depends(get_db),
    current_user:      User          = Depends(get_current_user),
):
    if not getattr(current_user, "is_admin", False):
        raise HTTPException(403, "Admin uniquement")
    bt = db.query(LootBoxType).filter(LootBoxType.id == box_type_id).first()
    if not bt:
        raise HTTPException(404, "Type de caisse introuvable")

    updates = {
        "name": name, "description": description, "pool_types": pool_types,
        "collection_filter": collection_filter, "price_coins": price_coins,
        "drop_common": drop_common, "drop_rare": drop_rare,
        "drop_epic": drop_epic, "drop_legendary": drop_legendary,
        "is_active": is_active,
    }
    for k, v in updates.items():
        if v is not None:
            setattr(bt, k, v)

    if file:
        if file.content_type not in ["image/jpeg", "image/png", "image/webp"]:
            raise HTTPException(400, "Format non supporté")
        contents = await file.read()
        safe_name = bt.name.lower().replace(" ", "_").replace("—", "-")
        bt.image_url = await upload_image(contents, folder="junglegap/lootboxes", public_id=f"box_{safe_name}")

    total = bt.drop_common + bt.drop_rare + bt.drop_epic + bt.drop_legendary
    if total != 100:
        db.rollback()
        raise HTTPException(400, f"Drop rates doivent totaliser 100 (actuel: {total})")

    db.commit()
    db.refresh(bt)
    return {"success": True, "id": bt.id, "image_url": bt.image_url}


# ─── ADMIN — DELETE /lootbox/admin/types/{id} ──────────────
@router.delete("/admin/types/{box_type_id}")
def admin_delete_box_type(
    box_type_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not getattr(current_user, "is_admin", False):
        raise HTTPException(403, "Admin uniquement")
    bt = db.query(LootBoxType).filter(LootBoxType.id == box_type_id).first()
    if not bt:
        raise HTTPException(404, "Type de caisse introuvable")

    has_boxes = db.query(LootBox).filter(LootBox.box_type_id == box_type_id).first() is not None
    if has_boxes:
        bt.is_active = False
        db.commit()
        return {"success": True, "mode": "soft", "message": "Désactivé (des caisses existent en circulation)"}

    db.delete(bt)
    db.commit()
    return {"success": True, "mode": "hard"}