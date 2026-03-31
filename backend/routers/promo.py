from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db
from models.user import User
from models.user_card import UserCard
from models.promo_code import PromoCode, PromoCodeUse
from deps import get_current_user

router = APIRouter(prefix="/promo", tags=["promo"])

# ─── Schemas ────────────────────────────────────────────────

class RedeemSchema(BaseModel):
    code: str

class CreatePromoSchema(BaseModel):
    code:         str
    description:  Optional[str] = None
    coins_amount: int            = 0
    card_id:      Optional[int] = None
    max_uses:     Optional[int] = None   # None = illimité au total

class TogglePromoSchema(BaseModel):
    is_active: bool

# ─── POST /promo/redeem ──────────────────────────────────────

@router.post("/redeem")
def redeem_code(
    body: RedeemSchema,
    db:   Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    code_str = body.code.strip().upper()

    promo = db.query(PromoCode).filter(PromoCode.code == code_str).first()

    # ── Validations ──
    if not promo or not promo.is_active:
        raise HTTPException(404, "Code introuvable ou expiré")

    if promo.max_uses is not None and promo.uses_count >= promo.max_uses:
        raise HTTPException(400, "Ce code a atteint son nombre maximum d'utilisations")

    already_used = db.query(PromoCodeUse).filter(
        PromoCodeUse.promo_code_id == promo.id,
        PromoCodeUse.user_id == current_user.id,
    ).first()
    if already_used:
        raise HTTPException(400, "Tu as déjà utilisé ce code")

    # ── Application des récompenses ──
    rewards = {}

    if promo.coins_amount > 0:
        current_user.coins += promo.coins_amount
        rewards["coins"] = promo.coins_amount

    if promo.card_id:
        # Vérifie que l'user n'a pas déjà la carte
        existing_card = db.query(UserCard).filter(
            UserCard.user_id == current_user.id,
            UserCard.card_id == promo.card_id,
        ).first()
        if not existing_card:
            db.add(UserCard(user_id=current_user.id, card_id=promo.card_id))
            rewards["card"] = {
                "name":      promo.card.name,
                "rarity":    promo.card.rarity,
                "image_url": promo.card.image_url,
            }

    # ── Enregistrement de l'utilisation ──
    db.add(PromoCodeUse(promo_code_id=promo.id, user_id=current_user.id))
    promo.uses_count += 1
    db.commit()

    return {
        "success":     True,
        "coins_total": current_user.coins,
        "rewards":     rewards,
    }

# ─── ADMIN — GET /promo/admin ────────────────────────────────

@router.get("/admin")
def list_promos(db: Session = Depends(get_db)):
    promos = db.query(PromoCode).order_by(PromoCode.created_at.desc()).all()
    return [_serialize(p) for p in promos]

# ─── ADMIN — POST /promo/admin ───────────────────────────────

@router.post("/admin")
def create_promo(body: CreatePromoSchema, db: Session = Depends(get_db)):
    code_str = body.code.strip().upper()
    if db.query(PromoCode).filter(PromoCode.code == code_str).first():
        raise HTTPException(400, "Ce code existe déjà")
    if body.coins_amount == 0 and body.card_id is None:
        raise HTTPException(400, "Un code doit donner au moins des coins ou une carte")

    promo = PromoCode(
        code=code_str,
        description=body.description,
        coins_amount=body.coins_amount,
        card_id=body.card_id,
        max_uses=body.max_uses,
    )
    db.add(promo)
    db.commit()
    db.refresh(promo)
    return _serialize(promo)

# ─── ADMIN — PATCH /promo/admin/{id} ────────────────────────

@router.patch("/admin/{promo_id}")
def toggle_promo(promo_id: int, body: TogglePromoSchema, db: Session = Depends(get_db)):
    promo = db.query(PromoCode).filter(PromoCode.id == promo_id).first()
    if not promo:
        raise HTTPException(404, "Code introuvable")
    promo.is_active = body.is_active
    db.commit()
    return _serialize(promo)

# ─── ADMIN — DELETE /promo/admin/{id} ───────────────────────

@router.delete("/admin/{promo_id}")
def delete_promo(promo_id: int, db: Session = Depends(get_db)):
    promo = db.query(PromoCode).filter(PromoCode.id == promo_id).first()
    if not promo:
        raise HTTPException(404, "Code introuvable")
    db.delete(promo)
    db.commit()
    return {"success": True}

# ─── Helper ─────────────────────────────────────────────────

def _serialize(p: PromoCode):
    return {
        "id":           p.id,
        "code":         p.code,
        "description":  p.description,
        "coins_amount": p.coins_amount,
        "card":         {"id": p.card.id, "name": p.card.name, "rarity": p.card.rarity} if p.card else None,
        "max_uses":     p.max_uses,
        "uses_count":   p.uses_count,
        "is_active":    p.is_active,
        "created_at":   p.created_at.isoformat() if p.created_at else None,
    }