from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.sql import func
from database import Base

class EsportsTeam(Base):
    __tablename__ = "esports_teams"

    id           = Column(Integer, primary_key=True)
    api_id       = Column(String(100), unique=True, nullable=True, index=True)
    slug         = Column(String(100), unique=True, nullable=True, index=True)
    code         = Column(String(20), nullable=False, index=True)
    name         = Column(String(200), nullable=False)
    logo_url     = Column(String, nullable=True)
    region       = Column(String(20), nullable=True)
    accent_color = Column(String(7), default='#00e5ff')
    is_active    = Column(Boolean, default=True)
    updated_at   = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())