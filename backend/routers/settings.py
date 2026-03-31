from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from database import get_db
from models.user import User
from deps import get_current_user

router = APIRouter(prefix="/settings", tags=["settings"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

# ─── Schemas ────────────────────────────────────────────────

class UpdateProfileSchema(BaseModel):
    username: str
    email:    EmailStr

class UpdatePasswordSchema(BaseModel):
    current_password: str
    new_password:     str

# ─── PATCH /settings/profile ────────────────────────────────

@router.patch("/profile")
def update_profile(
    body: UpdateProfileSchema,
    db:   Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    username = body.username.strip()
    email    = body.email.strip().lower()

    if len(username) < 3 or len(username) > 20:
        raise HTTPException(400, "Le pseudo doit faire entre 3 et 20 caractères")

    # Check unicité username (exclut l'utilisateur courant)
    conflict_user = db.query(User).filter(User.username == username, User.id != current_user.id).first()
    if conflict_user:
        raise HTTPException(400, "Ce pseudo est déjà pris")

    # Check unicité email
    conflict_email = db.query(User).filter(User.email == email, User.id != current_user.id).first()
    if conflict_email:
        raise HTTPException(400, "Cet email est déjà utilisé")

    current_user.username = username
    current_user.email    = email
    db.commit()

    return {
        "username": current_user.username,
        "email":    current_user.email,
    }

# ─── PATCH /settings/password ───────────────────────────────

@router.patch("/password")
def update_password(
    body: UpdatePasswordSchema,
    db:   Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not pwd_context.verify(body.current_password, current_user.password_hash):
        raise HTTPException(400, "Mot de passe actuel incorrect")

    if len(body.new_password) < 8:
        raise HTTPException(400, "Le nouveau mot de passe doit faire au moins 8 caractères")

    current_user.password_hash = pwd_context.hash(body.new_password)
    db.commit()

    return {"success": True}

# ─── DELETE /settings/account ───────────────────────────────

@router.delete("/account")
def delete_account(
    db:   Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db.delete(current_user)
    db.commit()
    return {"success": True}