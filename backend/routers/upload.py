from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from database import get_db
from models.user import User
from services.cloudinary_service import upload_image

router = APIRouter(prefix="/upload", tags=["upload"])

def get_current_user(token: str, db: Session) -> User:
    from jose import jwt, JWTError
    import os
    try:
        payload = jwt.decode(token, os.getenv("SECRET_KEY"), algorithms=["HS256"])
        user_id = int(payload["sub"])
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(401, "Utilisateur introuvable")
        return user
    except JWTError:
        raise HTTPException(401, "Token invalide")


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    authorization: str = "",
    db: Session = Depends(get_db)
):
    user = get_current_user(authorization.replace("Bearer ", ""), db)

    if file.content_type not in ["image/jpeg", "image/png", "image/webp"]:
        raise HTTPException(400, "Format non supporté (jpeg, png, webp uniquement)")

    if file.size > 5 * 1024 * 1024:
        raise HTTPException(400, "Fichier trop lourd (5MB max)")

    contents = await file.read()
    url = await upload_image(contents, folder="junglegap/avatars", public_id=f"avatar_{user.id}")

    user.avatar_url = url
    db.commit()

    return { "avatar_url": url }


@router.post("/pro-player/{player_id}")
async def upload_pro_photo(
    player_id: int,
    file: UploadFile = File(...),
    authorization: str = "",
    db: Session = Depends(get_db)
):
    user = get_current_user(authorization.replace("Bearer ", ""), db)

    from models.pro_player import ProPlayer
    pro = db.query(ProPlayer).filter(ProPlayer.id == player_id).first()
    if not pro:
        raise HTTPException(404, "Joueur introuvable")

    if file.content_type not in ["image/jpeg", "image/png", "image/webp"]:
        raise HTTPException(400, "Format non supporté")

    contents = await file.read()
    url = await upload_image(contents, folder="junglegap/pros", public_id=f"pro_{player_id}")

    pro.photo_url = url
    db.commit()

    return { "photo_url": url }