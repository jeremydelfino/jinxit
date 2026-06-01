"""Myceo — saison de compétition (1 active par franchise ; 3 splits/an)."""
from sqlalchemy import Column, Integer, SmallInteger, String, ForeignKey, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.sql import func
from database import Base


class GmSeason(Base):
    __tablename__ = "gm_seasons"

    id               = Column(Integer, primary_key=True)
    team_id          = Column(Integer, ForeignKey("gm_teams.id", ondelete="CASCADE"), nullable=False)
    league           = Column(String(10), nullable=False, default="LFL")
    year             = Column(SmallInteger, nullable=False)
    split_no         = Column(SmallInteger, nullable=False, default=1)
    phase            = Column(String(12), nullable=False, default="REGULAR")
    current_matchday = Column(SmallInteger, nullable=False, default=1)
    total_matchdays  = Column(SmallInteger, nullable=False, default=9)
    created_at       = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        CheckConstraint("phase IN ('REGULAR','PLAYOFFS','DONE')", name="ck_gm_season_phase"),
        CheckConstraint("split_no BETWEEN 1 AND 3",               name="ck_gm_season_split"),
        Index("idx_gm_seasons_team", "team_id"),
    )