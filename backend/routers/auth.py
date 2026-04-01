from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
from pydantic import BaseModel, EmailStr
from database import get_db
from models.user import User
from services import riot
from services.email_service import send_verification_code
import os
import random

router = APIRouter(prefix="/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
SECRET_KEY = os.getenv("SECRET_KEY")

# ─── Schemas ────────────────────────────────────────────────

class RegisterSchema(BaseModel):
    username: str
    email:    EmailStr
    password: str

class LoginSchema(BaseModel):
    email:    EmailStr
    password: str

class RiotInitSchema(BaseModel):
    email:     EmailStr
    game_name: str
    tag_line:  str
    region:    str

class RegisterCompleteSchema(BaseModel):
    username:         str
    email:            EmailStr
    password:         str
    game_name:        str
    tag_line:         str
    region:           str
    expected_icon_id: int

class VerifyEmailSchema(BaseModel):
    email: EmailStr
    code:  str

class ResendCodeSchema(BaseModel):
    email: EmailStr

# ─── Helpers ────────────────────────────────────────────────

def create_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(days=7)
    return jwt.encode({"sub": str(user_id), "exp": expire}, SECRET_KEY, algorithm="HS256")

def validate_new_user(username: str, email: str, db: Session):
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(400, "Email déjà utilisé")
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(400, "Username déjà pris")

def _generate_and_save_code(user: User, db: Session) -> str:
    code = str(random.randint(100000, 999999))
    user.email_code            = code
    user.email_code_expires_at = datetime.utcnow() + timedelta(minutes=10)
    db.commit()
    return code

# ─── POST /register/init-riot ────────────────────────────────

@router.post("/register/init-riot")
async def register_init_riot(body: RiotInitSchema, db: Session = Depends(get_db)):
    try:
        account = await riot.get_account_by_riot_id(body.game_name, body.tag_line, body.region)
    except Exception:
        raise HTTPException(400, "Riot ID introuvable — vérifie le pseudo et le tag")

    puuid = account["puuid"]

    existing = db.query(User).filter(User.riot_puuid == puuid).first()
    if existing:
        raise HTTPException(400, "Ce compte Riot est déjà lié à un compte JungleGap")

    icon_id  = random.randint(1, 28)
    icon_url = f"https://ddragon.leagueoflegends.com/cdn/16.7.1/img/profileicon/{icon_id}.png"

    return {
        "puuid":     puuid,
        "icon_id":   icon_id,
        "icon_url":  icon_url,
        "game_name": body.game_name,
        "tag_line":  body.tag_line,
    }

# ─── POST /register/complete ─────────────────────────────────

@router.post("/register/complete")
async def register_complete(body: RegisterCompleteSchema, db: Session = Depends(get_db)):
    validate_new_user(body.username, body.email, db)

    try:
        account = await riot.get_account_by_riot_id(body.game_name, body.tag_line, body.region)
    except Exception:
        raise HTTPException(400, "Riot ID introuvable")

    puuid = account["puuid"]

    if db.query(User).filter(User.riot_puuid == puuid).first():
        raise HTTPException(400, "Ce compte Riot est déjà lié à un compte JungleGap")

    try:
        summoner     = await riot.get_summoner_by_puuid(puuid, body.region)
        current_icon = summoner["profileIconId"]
    except Exception:
        raise HTTPException(400, "Impossible de récupérer le profil Riot")

    if current_icon != body.expected_icon_id:
        raise HTTPException(
            400,
            f"Mauvaise icône détectée (actuelle : {current_icon}, attendue : {body.expected_icon_id}). "
            "Si jamais votre ID d'icone ne change pas, attendez quelques minutes et relancer l'étape d'inscription."
        )

    user = User(
        username=body.username,
        email=body.email,
        password_hash=pwd_context.hash(body.password),
        riot_puuid=puuid,
        email_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    code = _generate_and_save_code(user, db)
    send_verification_code(body.email, code, user.username)

    return {
        "email":                      body.email,
        "username":                   user.username,
        "coins":                      user.coins,
        "email_verification_required": True,
    }

# ─── POST /register (sans Riot) ──────────────────────────────

@router.post("/register")
def register(body: RegisterSchema, db: Session = Depends(get_db)):
    validate_new_user(body.username, body.email, db)
    user = User(
        username=body.username,
        email=body.email,
        password_hash=pwd_context.hash(body.password),
        email_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    code = _generate_and_save_code(user, db)
    send_verification_code(body.email, code, user.username)

    return {
        "email":                      body.email,
        "username":                   user.username,
        "coins":                      user.coins,
        "email_verification_required": True,
    }

# ─── POST /register/verify-email ─────────────────────────────

@router.post("/register/verify-email")
def verify_email(body: VerifyEmailSchema, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user:
        raise HTTPException(404, "Utilisateur introuvable")
    if user.email_verified:
        return {"token": create_token(user.id), "username": user.username, "coins": user.coins}
    if not user.email_code:
        raise HTTPException(400, "Aucun code en attente — demande un renvoi")
    if user.email_code_expires_at < datetime.utcnow():
        raise HTTPException(400, "Code expiré — demande un nouveau code")
    if user.email_code != body.code.strip():
        raise HTTPException(400, "Code incorrect")

    user.email_verified        = True
    user.email_code            = None
    user.email_code_expires_at = None
    db.commit()

    return {
        "token":    create_token(user.id),
        "username": user.username,
        "coins":    user.coins,
    }

# ─── POST /register/resend-code ──────────────────────────────

@router.post("/register/resend-code")
def resend_code(body: ResendCodeSchema, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user:
        raise HTTPException(404, "Utilisateur introuvable")
    if user.email_verified:
        raise HTTPException(400, "Email déjà vérifié")

    code = _generate_and_save_code(user, db)
    send_verification_code(body.email, code, user.username)

    return {"success": True, "message": "Code renvoyé"}

# ─── POST /login ─────────────────────────────────────────────

@router.post("/login")
def login(body: LoginSchema, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not pwd_context.verify(body.password, user.password_hash):
        raise HTTPException(401, "Identifiants incorrects")
    return {
        "token":          create_token(user.id),
        "username":       user.username,
        "coins":          user.coins,
        "email_verified": user.email_verified,
    }