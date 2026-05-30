"""
Champion pool par équipe Pro et par rôle (KC / G2 / T1), pondéré par récence.
Alimenté par services/team_pool_scraper.py depuis Leaguepedia (ScoreboardPlayers).
"""
from sqlalchemy import Column, Integer, String, Float, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.sql import func
from database import Base


class TeamChampionPool(Base):
    __tablename__ = "team_champion_pool"

    id          = Column(Integer, primary_key=True)
    team_code   = Column(String(10), nullable=False)   # KC | G2 | T1
    lane        = Column(String(20), nullable=False)   # TOP | JUNGLE | MID | ADC | SUPPORT
    champion    = Column(String(50), nullable=False)
    weight      = Column(Float, nullable=False, default=0.0)   # part dans la lane (0–1)
    n_games     = Column(Float, nullable=False, default=0.0)   # games pondérées récence
    last_played = Column(TIMESTAMP)
    updated_at  = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("team_code", "lane", "champion", name="uq_team_pool"),
        Index("idx_team_pool_lookup", "team_code", "lane"),
    )