"""Myceo — event aléatoire (blessure, méta, visa, morale…)."""
from sqlalchemy import Column, Integer, SmallInteger, String, Text, Boolean, ForeignKey, Index
from sqlalchemy.dialects.postgresql import TIMESTAMP, JSONB
from sqlalchemy.sql import func
from database import Base


class GmEvent(Base):
    __tablename__ = "gm_events"

    id          = Column(Integer, primary_key=True)
    team_id     = Column(Integer, ForeignKey("gm_teams.id", ondelete="CASCADE"), nullable=False)
    season_id   = Column(Integer, ForeignKey("gm_seasons.id", ondelete="CASCADE"))
    matchday    = Column(SmallInteger)
    type        = Column(String(16), nullable=False)
    payload     = Column(JSONB, nullable=False, default=dict, server_default="{}")
    message     = Column(Text)
    is_resolved = Column(Boolean, nullable=False, default=False)
    created_at  = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        Index("idx_gm_events_team", "team_id"),
    )