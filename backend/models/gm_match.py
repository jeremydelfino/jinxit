"""Myceo — match = série (BO1 régulière, BO3/BO5 playoffs). ai_id NULL = la franchise."""
from sqlalchemy import Column, Integer, SmallInteger, String, Boolean, ForeignKey, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import TIMESTAMP
from database import Base


class GmMatch(Base):
    __tablename__ = "gm_matches"

    id            = Column(Integer, primary_key=True)
    season_id     = Column(Integer, ForeignKey("gm_seasons.id", ondelete="CASCADE"), nullable=False)
    phase         = Column(String(8), nullable=False, default="REGULAR")
    matchday      = Column(SmallInteger)
    round_label   = Column(String(20))
    home_ai_id    = Column(Integer, ForeignKey("gm_ai_teams.id"))   # NULL = user
    away_ai_id    = Column(Integer, ForeignKey("gm_ai_teams.id"))   # NULL = user
    format        = Column(String(4), nullable=False, default="BO1")
    score_home    = Column(SmallInteger, nullable=False, default=0)
    score_away    = Column(SmallInteger, nullable=False, default=0)
    status        = Column(String(12), nullable=False, default="SCHEDULED")
    winner_side   = Column(String(4))
    involves_user = Column(Boolean, nullable=False, default=False)
    played_at     = Column(TIMESTAMP)

    __table_args__ = (
        CheckConstraint("phase IN ('REGULAR','SEMI','FINAL')",                   name="ck_gm_match_phase"),
        CheckConstraint("format IN ('BO1','BO3','BO5')",                         name="ck_gm_match_format"),
        CheckConstraint("status IN ('SCHEDULED','DRAFTING','PLAYED')",           name="ck_gm_match_status"),
        CheckConstraint("winner_side IS NULL OR winner_side IN ('HOME','AWAY')", name="ck_gm_match_winner"),
        Index("idx_gm_matches_season", "season_id"),
        Index("idx_gm_matches_user",   "involves_user"),
    )