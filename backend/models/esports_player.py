# backend/models/esports_player.py
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.sql import func
from database import Base

class EsportsPlayer(Base):
    __tablename__ = "esports_players"

    id           = Column(Integer, primary_key=True)
    api_id       = Column(String(100), unique=True, nullable=True, index=True)
    summoner_name = Column(String(100), nullable=True)
    first_name   = Column(String(100), nullable=True)
    last_name    = Column(String(100), nullable=True)
    role         = Column(String(20), nullable=True)    # "top","jungle","mid","bottom","support"
    photo_url    = Column(String, nullable=True)         # depuis API LoL Esports
    team_code    = Column(String(20), nullable=True)     # "T1", "G2", etc.
    team_name    = Column(String(200), nullable=True)
    region       = Column(String(20), nullable=True)
    riot_puuid   = Column(String(100), unique=True, nullable=True, index=True)
    is_starter   = Column(Boolean, default=True)
    is_active    = Column(Boolean, default=True)
    updated_at   = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())