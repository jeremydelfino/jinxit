from sqlalchemy import Column, Integer, String, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.sql import func
from database import Base

class RiotAccount(Base):
    __tablename__ = "riot_accounts"

    id                   = Column(Integer, primary_key=True)
    user_id              = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    riot_puuid           = Column(String(100), unique=True, nullable=False)
    summoner_name        = Column(String(100), nullable=True)
    tag_line             = Column(String(50), nullable=True)
    region               = Column(String(20), nullable=True)
    profile_icon_id      = Column(Integer, nullable=True)
    profile_icon_url     = Column(String, nullable=True)
    tier                 = Column(String(30), nullable=True)
    rank                 = Column(String(10), nullable=True)
    lp                   = Column(Integer, nullable=True)
    is_primary           = Column(Boolean, default=False)
    verification_icon    = Column(Integer, nullable=True)
    created_at           = Column(TIMESTAMP, server_default=func.now())