from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
from pydantic import BaseModel, EmailStr
from database import get_db
from models.user import User
from services import riot
import os
import random

router = APIRouter(prefix="/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
SECRET_KEY = os.getenv("SECRET_KEY")

# ─── Schemas ────────────────────────────────────────────────

class RegisterSchema(BaseModel):
    username: str
    email: EmailStr
    password: str

class LoginSchema(BaseModel):
    email: EmailStr
    password: str

class RiotInitSchema(BaseModel):
    """Step 2 : demande l'icône de vérification pour un Riot ID"""
    email: EmailStr          # pour retrouver le pending user
    game_name: str
    tag_line: str
    region: str

class RegisterCompleteSchema(BaseModel):
    """Step 3 : crée le compte si l'icône Riot correspond"""
    username: str
    email: EmailStr
    password: str
    game_name: str
    tag_line: str
    region: str
    expected_icon_id: int    # icône qu'on avait demandé à l'user d'équiper

# ─── Helpers ────────────────────────────────────────────────

def create_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(days=7)
    return jwt.encode({"sub": str(user_id), "exp": expire}, SECRET_KEY, algorithm="HS256")

def validate_new_user(body_username: str, body_email: str, db: Session):
    if db.query(User).filter(User.email == body_email).first():
        raise HTTPException(400, "Email déjà utilisé")
    if db.query(User).filter(User.username == body_username).first():
        raise HTTPException(400, "Username déjà pris")

# ─── Routes ─────────────────────────────────────────────────

@router.post("/register/init-riot")
async def register_init_riot(body: RiotInitSchema, db: Session = Depends(get_db)):
    """
    Étape 2 du register : vérifie que le Riot ID existe et retourne
    l'icône aléatoire à équiper pour prouver que c'est bien son compte.
    """
    # Vérifier que le Riot ID existe via l'API Riot
    try:
        account = await riot.get_account_by_riot_id(body.game_name, body.tag_line, body.region)
    except Exception:
        raise HTTPException(400, "Riot ID introuvable — vérifie le pseudo et le tag")

    puuid = account["puuid"]

    # Vérifier que ce puuid n'est pas déjà lié à un autre compte Jinxit
    existing = db.query(User).filter(User.riot_puuid == puuid).first()
    if existing:
        raise HTTPException(400, "Ce compte Riot est déjà lié à un compte Jinxit")

    # Générer une icône de vérification aléatoire (icônes de base LoL 1-28)
    icon_id = random.randint(1, 28)
    icon_url = f"https://ddragon.leagueoflegends.com/cdn/14.10.1/img/profileicon/{icon_id}.png"

    return {
        "puuid": puuid,
        "icon_id": icon_id,
        "icon_url": icon_url,
        "game_name": body.game_name,
        "tag_line": body.tag_line,
    }


@router.post("/register/complete")
async def register_complete(body: RegisterCompleteSchema, db: Session = Depends(get_db)):
    """
    Étape 3 du register : vérifie l'icône Riot puis crée le compte.
    """
    # Validation des champs
    validate_new_user(body.username, body.email, db)

    # Récupérer le puuid
    try:
        account = await riot.get_account_by_riot_id(body.game_name, body.tag_line, body.region)
    except Exception:
        raise HTTPException(400, "Riot ID introuvable")

    puuid = account["puuid"]

    # Vérifier une dernière fois que le puuid n'est pas pris
    if db.query(User).filter(User.riot_puuid == puuid).first():
        raise HTTPException(400, "Ce compte Riot est déjà lié à un compte Jinxit")

    # Vérifier l'icône actuelle du joueur
    try:
        summoner = await riot.get_summoner_by_puuid(puuid, body.region)
        current_icon = summoner["profileIconId"]
    except Exception:
        raise HTTPException(400, "Impossible de récupérer le profil Riot")

    if current_icon != body.expected_icon_id:
        raise HTTPException(
            400,
            f"Mauvaise icône détectée (icône actuelle : {current_icon}, attendue : {body.expected_icon_id}). "
            f"Change bien ton icône dans LoL et réessaie."
        )

    # ✅ Tout est bon — créer le compte
    user = User(
        username=body.username,
        email=body.email,
        password_hash=pwd_context.hash(body.password),
        riot_puuid=puuid,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "token": create_token(user.id),
        "username": user.username,
        "coins": user.coins,
        "riot_linked": True,
    }


@router.post("/register")
def register(body: RegisterSchema, db: Session = Depends(get_db)):
    """Route register classique conservée pour compatibilité."""
    validate_new_user(body.username, body.email, db)
    user = User(
        username=body.username,
        email=body.email,
        password_hash=pwd_context.hash(body.password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"token": create_token(user.id), "username": user.username, "coins": user.coins}


@router.post("/login")
def login(body: LoginSchema, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not pwd_context.verify(body.password, user.password_hash):
        raise HTTPException(401, "Identifiants incorrects")
    return {"token": create_token(user.id), "username": user.username, "coins": user.coins}