from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.sql import func
from database import Base

class ProPlayer(Base):
    __tablename__ = "pro_players"

    id           = Column(Integer, primary_key=True)
    name         = Column(String(100), nullable=False)
    team         = Column(String(100), nullable=True)
    role         = Column(String(20), nullable=True)
    photo_url    = Column(String, nullable=True)
    riot_puuid   = Column(String(100), unique=True, nullable=True)
    region       = Column(String(10), nullable=True)
    accent_color = Column(String(7), default='#00e5ff')
    is_active    = Column(Boolean, default=True)
    created_at   = Column(TIMESTAMP, server_default=func.now())
    team_logo_url = Column(String(500), nullable=True)