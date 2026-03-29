from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import TIMESTAMP, JSONB
from sqlalchemy.sql import func
from database import Base

class Notification(Base):
    __tablename__ = "notifications"

    id          = Column(Integer, primary_key=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=False)
    type        = Column(String(50), nullable=False)   # ex: "favorite_live"
    message     = Column(String(255), nullable=False)
    data        = Column(JSONB, nullable=True)          # { game_id, player_name, region, ... }
    read        = Column(Boolean, default=False)
    created_at  = Column(TIMESTAMP, server_default=func.now())