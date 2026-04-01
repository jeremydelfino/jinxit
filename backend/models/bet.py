from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.sql import func
from database import Base

class Bet(Base):
    __tablename__ = "bets"

    id              = Column(Integer, primary_key=True)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False)
    live_game_id    = Column(Integer, ForeignKey("live_games.id"), nullable=False)
    card_used_id    = Column(Integer, ForeignKey("cards.id"), nullable=True)
    bet_type_slug   = Column(String(50), ForeignKey("bet_types.slug"), nullable=False)
    bet_value       = Column(String(100), nullable=False)
    amount          = Column(Integer, nullable=False)
    odds            = Column(Float, default=2.0)
    boost_applied   = Column(Float, default=0)
    status          = Column(String(20), default="pending")
    payout          = Column(Integer, default=0)
    slip_id         = Column(String(36), nullable=True)
    created_at      = Column(TIMESTAMP, server_default=func.now())