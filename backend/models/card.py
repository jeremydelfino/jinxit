from sqlalchemy import Column, Integer, String, Boolean, Float, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.sql import func
from database import Base

class Card(Base):
    __tablename__ = "cards"

    id              = Column(Integer, primary_key=True)
    name            = Column(String(100), nullable=False)
    type            = Column(String(50), nullable=False)
    rarity          = Column(String(20), nullable=False)
    image_url       = Column(String, nullable=False)
    boost_type      = Column(String(50), nullable=True)
    boost_value     = Column(Float, default=0)
    trigger_type    = Column(String(20), nullable=True)
    trigger_value   = Column(String(100), nullable=True)
    is_banner       = Column(Boolean, default=False)
    is_title        = Column(Boolean, default=False)
    title_text      = Column(String(100), nullable=True)
    collection      = Column(String(100), nullable=True)
    artist          = Column(String(100), nullable=True)
    lore            = Column(Text, nullable=True)
    created_at      = Column(TIMESTAMP, server_default=func.now())