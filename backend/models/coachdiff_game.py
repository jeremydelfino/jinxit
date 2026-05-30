"""
Parties de CoachDiff : draft 1v1 contre un bot, scoring final /100.
"""
from sqlalchemy import Column, Integer, String, Float, ForeignKey, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import TIMESTAMP, JSONB
from sqlalchemy.sql import func
from database import Base


class CoachDiffGame(Base):
    __tablename__ = "coachdiff_games"

    id              = Column(Integer, primary_key=True)
    user_id         = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    status          = Column(String(20), nullable=False, default="in_progress")
    user_side       = Column(String(10), nullable=False)
    bot_side        = Column(String(10), nullable=False)

    opponent        = Column(String(10))   # KC | G2 | T1 (nullable pour les vieilles games)

    user_score      = Column(Float)
    bot_score       = Column(Float)
    user_breakdown  = Column(JSONB)
    bot_breakdown   = Column(JSONB)
    winner          = Column(String(10))
    coins_delta     = Column(Integer, nullable=False, default=0)

    draft_state     = Column(JSONB, nullable=False)

    created_at      = Column(TIMESTAMP, server_default=func.now())
    finished_at     = Column(TIMESTAMP)

    __table_args__ = (
        CheckConstraint("status IN ('in_progress','finished','cancelled')", name="ck_status"),
        CheckConstraint("user_side IN ('BLUE','RED')",                       name="ck_user_side"),
        CheckConstraint("bot_side IN ('BLUE','RED')",                        name="ck_bot_side"),
        CheckConstraint("winner IS NULL OR winner IN ('USER','BOT','DRAW')", name="ck_winner"),
        Index("idx_coachdiff_user",   "user_id"),
        Index("idx_coachdiff_status", "status"),
    )