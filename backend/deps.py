"""
deps.py — dépendance partagée pour récupérer l'utilisateur courant
via le header Authorization: Bearer <token>
"""
from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session
from database import get_db
from models.user import User
from jose import jwt, JWTError
import os


def get_current_user(
    authorization: str = Header(..., description="Bearer <token>"),
    db: Session = Depends(get_db),
) -> User:
    token = authorization.replace("Bearer ", "").strip()
    try:
        payload = jwt.decode(token, os.getenv("SECRET_KEY"), algorithms=["HS256"])
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(401, "Token invalide")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(401, "Utilisateur introuvable")
    return user