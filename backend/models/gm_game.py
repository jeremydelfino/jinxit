"""Myceo — une draft d'une série (matchs du user uniquement)."""
from sqlalchemy import Column, Integer, SmallInteger, String, Float, ForeignKey, CheckConstraint, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import TIMESTAMP, JSONB
from sqlalchemy.sql import func
from database import Base


class GmGame(Base):
    __tablename__ = "gm_games"

    id            = Column(Integer, primary_key=True)
    match_id      = Column(Integer, ForeignKey("gm_matches.id", ondelete="CASCADE"), nullable=False)
    game_no       = Column(SmallInteger, nullable=False, default=1)
    user_side     = Column(String(4))
    draft_state   = Column(JSONB)
    draft_user    = Column(Float)
    draft_opp     = Column(Float)
    strength_user = Column(Float)
    strength_opp  = Column(Float)
    mental_user   = Column(Float)
    mental_opp    = Column(Float)
    p_win         = Column(Float)
    result        = Column(String(4))
    status        = Column(String(12), nullable=False, default="DRAFTING")
    played_at     = Column(TIMESTAMP)
    created_at    = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("match_id", "game_no", name="uq_gm_game"),
        CheckConstraint("result IS NULL OR result IN ('WIN','LOSS')",       name="ck_gm_game_result"),
        CheckConstraint("user_side IS NULL OR user_side IN ('BLUE','RED')", name="ck_gm_game_side"),
        Index("idx_gm_games_match", "match_id"),
    )