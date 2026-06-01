"""Myceo — équipe IA (skin LFL au-dessus d'un bot_tier CoachDiff). Pool global."""
from sqlalchemy import Column, Integer, SmallInteger, String, Text, Boolean, CheckConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.sql import func
from database import Base


class GmAiTeam(Base):
    __tablename__ = "gm_ai_teams"

    id            = Column(Integer, primary_key=True)
    name          = Column(String(60), nullable=False)
    logo_url      = Column(Text)
    region        = Column(String(10), nullable=False, default="LFL")
    bot_tier      = Column(String(4), nullable=False, default="G2")
    base_strength = Column(SmallInteger, nullable=False, default=70)
    seed          = Column(SmallInteger, nullable=False, default=0)
    is_active     = Column(Boolean, nullable=False, default=True)
    created_at    = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        CheckConstraint("bot_tier IN ('LFL','KC','G2','T1')", name="ck_gm_ai_tier"),
    )