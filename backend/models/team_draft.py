"""Compos réelles (5 champs role-taggés, IDs DDragon) jouées par KC / G2 / T1."""
from sqlalchemy import Column, Integer, String, Float, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import TIMESTAMP, JSONB
from sqlalchemy.sql import func
from database import Base


class TeamDraft(Base):
    __tablename__ = "team_drafts"

    id          = Column(Integer, primary_key=True)
    team_code   = Column(String(10), nullable=False)
    game_id     = Column(String(40), nullable=False)
    comp        = Column(JSONB, nullable=False)
    weight      = Column(Float, nullable=False, default=0.0)
    played_at   = Column(TIMESTAMP)
    updated_at  = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("team_code", "game_id", name="uq_team_draft"),
        Index("idx_team_drafts_team", "team_code"),
    )