from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.sql import func
from database import Base

class User(Base):
    __tablename__ = "users"

    id                      = Column(Integer, primary_key=True)
    username                = Column(String(50), unique=True, nullable=False)
    email                   = Column(String(255), unique=True, nullable=False)
    password_hash           = Column(String, nullable=False)
    coins                   = Column(Integer, default=500)
    avatar_url              = Column(String, nullable=True)
    equipped_banner_id      = Column(Integer, ForeignKey("cards.id"), nullable=True)
    equipped_title_id       = Column(Integer, ForeignKey("cards.id"), nullable=True)
    last_daily              = Column(TIMESTAMP, nullable=True)
    riot_puuid              = Column(String(100), unique=True, nullable=True)
    riot_verification_icon  = Column(Integer, nullable=True)
    favorite_team_name      = Column(String(100), nullable=True)
    favorite_team_logo      = Column(String, nullable=True)
    favorite_team_color     = Column(String(20), nullable=True)
    created_at              = Column(TIMESTAMP, server_default=func.now())