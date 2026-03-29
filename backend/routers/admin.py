from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db
from models.pro_player import ProPlayer
from models.card import Card
from services.riot import get_account_by_riot_id
from services.cloudinary_service import upload_image

router = APIRouter(prefix="/admin", tags=["admin"])

# ─── PROS ────────────────────────────────────────────────────────────────────

class LinkAccountSchema(BaseModel):
    pro_id: int
    game_name: str
    tag: str
    region: str

class UpdateProSchema(BaseModel):
    name: str | None = None
    team: str | None = None
    role: str | None = None
    region: str | None = None
    accent_color: str | None = None
    is_active: bool | None = None

class CreateProSchema(BaseModel):
    name: str
    team: str
    role: str
    region: str
    accent_color: str = "#00e5ff"

@router.get("/pros")
def list_pros(db: Session = Depends(get_db)):
    pros = db.query(ProPlayer).order_by(ProPlayer.region, ProPlayer.team, ProPlayer.role).all()
    return [
        {
            "id": p.id, "name": p.name, "team": p.team, "role": p.role,
            "region": p.region, "accent_color": p.accent_color,
            "has_puuid": p.riot_puuid is not None, "riot_puuid": p.riot_puuid,
            "photo_url": p.photo_url, "is_active": p.is_active,
        }
        for p in pros
    ]

@router.post("/pros/link-account")
async def link_account(body: LinkAccountSchema, db: Session = Depends(get_db)):
    pro = db.query(ProPlayer).filter(ProPlayer.id == body.pro_id).first()
    if not pro:
        raise HTTPException(404, "Joueur introuvable")
    try:
        account = await get_account_by_riot_id(body.game_name, body.tag, body.region)
        puuid = account["puuid"]
        existing = db.query(ProPlayer).filter(ProPlayer.riot_puuid == puuid, ProPlayer.id != body.pro_id).first()
        if existing:
            raise HTTPException(400, f"Ce compte est déjà lié à {existing.name} ({existing.team})")
        pro.riot_puuid = puuid
        db.commit()
        return {"success": True, "pro": pro.name, "account": f"{body.game_name}#{body.tag}", "puuid": puuid[:20] + "..."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, str(e))

@router.delete("/pros/{pro_id}")
def delete_pro(pro_id: int, db: Session = Depends(get_db)):
    pro = db.query(ProPlayer).filter(ProPlayer.id == pro_id).first()
    if not pro:
        raise HTTPException(404, "Joueur introuvable")
    db.delete(pro)
    db.commit()
    return {"success": True, "deleted": pro.name}

@router.put("/pros/{pro_id}")
def update_pro(pro_id: int, body: UpdateProSchema, db: Session = Depends(get_db)):
    pro = db.query(ProPlayer).filter(ProPlayer.id == pro_id).first()
    if not pro:
        raise HTTPException(404, "Joueur introuvable")
    if body.name is not None: pro.name = body.name
    if body.team is not None: pro.team = body.team
    if body.role is not None: pro.role = body.role
    if body.region is not None: pro.region = body.region
    if body.accent_color is not None: pro.accent_color = body.accent_color
    if body.is_active is not None: pro.is_active = body.is_active
    db.commit()
    return {"success": True, "pro": pro.name}

@router.post("/pros")
def create_pro(body: CreateProSchema, db: Session = Depends(get_db)):
    pro = ProPlayer(name=body.name, team=body.team, role=body.role, region=body.region, accent_color=body.accent_color, is_active=True)
    db.add(pro)
    db.commit()
    db.refresh(pro)
    return {"success": True, "id": pro.id, "name": pro.name}

@router.delete("/pros/{pro_id}/unlink")
def unlink_account(pro_id: int, db: Session = Depends(get_db)):
    pro = db.query(ProPlayer).filter(ProPlayer.id == pro_id).first()
    if not pro:
        raise HTTPException(404, "Joueur introuvable")
    pro.riot_puuid = None
    db.commit()
    return {"success": True, "pro": pro.name}


# ─── CARDS ───────────────────────────────────────────────────────────────────

@router.get("/cards")
def list_cards(db: Session = Depends(get_db)):
    cards = db.query(Card).order_by(Card.rarity, Card.name).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "type": c.type,
            "rarity": c.rarity,
            "image_url": c.image_url,
            "boost_type": c.boost_type,
            "boost_value": c.boost_value,
            "trigger_type": c.trigger_type,
            "trigger_value": c.trigger_value,
            "is_banner": c.is_banner,
            "is_title": c.is_title,
            "title_text": c.title_text,
        }
        for c in cards
    ]

@router.post("/cards")
async def create_card(
    # Champs de la carte
    name:          str           = Form(...),
    type:          str           = Form(...),           # champion | pro_player | meme | cosmetic
    rarity:        str           = Form(...),           # common | rare | epic | legendary
    # Effet
    boost_type:    Optional[str] = Form(None),          # percent_gain | flat_gain
    boost_value:   Optional[float] = Form(0.0),
    trigger_type:  Optional[str] = Form(None),          # champion | player | mechanic | any
    trigger_value: Optional[str] = Form(None),          # "Yasuo", "Faker", "first_blood"...
    # Cosmétiques
    is_banner:     bool          = Form(False),
    is_title:      bool          = Form(False),
    title_text:    Optional[str] = Form(None),
    # Image
    file:          UploadFile    = File(...),
    db:            Session       = Depends(get_db),
):
    # Validation
    if rarity not in ("common", "rare", "epic", "legendary"):
        raise HTTPException(400, "Rareté invalide")
    if type not in ("champion", "pro_player", "meme", "cosmetic"):
        raise HTTPException(400, "Type invalide")
    if file.content_type not in ["image/jpeg", "image/png", "image/webp"]:
        raise HTTPException(400, "Format non supporté (jpeg, png, webp)")

    contents = await file.read()
    # Nom de fichier propre pour Cloudinary
    safe_name = name.lower().replace(" ", "_").replace("—", "-")
    image_url = await upload_image(contents, folder="junglegap/cards", public_id=f"card_{safe_name}_{rarity}")

    card = Card(
        name=name,
        type=type,
        rarity=rarity,
        image_url=image_url,
        boost_type=boost_type,
        boost_value=boost_value or 0.0,
        trigger_type=trigger_type,
        trigger_value=trigger_value,
        is_banner=is_banner,
        is_title=is_title,
        title_text=title_text,
    )
    db.add(card)
    db.commit()
    db.refresh(card)

    return {
        "success": True,
        "id": card.id,
        "name": card.name,
        "rarity": card.rarity,
        "image_url": card.image_url,
    }

@router.delete("/cards/{card_id}")
def delete_card(card_id: int, db: Session = Depends(get_db)):
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(404, "Carte introuvable")
    db.delete(card)
    db.commit()
    return {"success": True, "deleted": card.name}