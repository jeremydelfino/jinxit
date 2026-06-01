"""Myceo — classement d'une saison (1 ligne par compétiteur ; ai_team_id NULL = la franchise)."""
from sqlalchemy import Column, Integer, SmallInteger, ForeignKey, UniqueConstraint, Index
from database import Base


class GmStanding(Base):
    __tablename__ = "gm_standings"

    id         = Column(Integer, primary_key=True)
    season_id  = Column(Integer, ForeignKey("gm_seasons.id", ondelete="CASCADE"), nullable=False)
    ai_team_id = Column(Integer, ForeignKey("gm_ai_teams.id"))   # NULL = user
    wins       = Column(SmallInteger, nullable=False, default=0)
    losses     = Column(SmallInteger, nullable=False, default=0)
    points     = Column(SmallInteger, nullable=False, default=0)
    played     = Column(SmallInteger, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("season_id", "ai_team_id", name="uq_gm_standing"),
        Index("idx_gm_standings_season", "season_id"),
    )