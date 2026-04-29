"""
Stats agrégées par champion / tier / lane / région.
Mises à jour par champion_winrate_collector.
"""
from sqlalchemy import Column, Integer, String, Float, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.sql import func
from database import Base


class ChampionStats(Base):
    __tablename__ = "champion_stats"

    id          = Column(Integer, primary_key=True)
    champion    = Column(String(50), nullable=False)
    tier        = Column(String(20), nullable=False)   # MASTER (regroupé Master/GM/Challenger)
    lane        = Column(String(20), nullable=False)   # TOP | JUNGLE | MID | ADC | SUPPORT | ALL
    region      = Column(String(10), nullable=False)   # EUW | KR | ALL

    n_games     = Column(Integer, default=0)
    wins        = Column(Integer, default=0)
    winrate     = Column(Float, default=0.50)
    pickrate    = Column(Float, default=0.0)           # # games / total games du tier
    banrate     = Column(Float, default=0.0)           # rempli si data dispo (souvent 0)

    avg_kda     = Column(Float, default=0.0)
    avg_kp      = Column(Float, default=0.0)           # kill participation

    updated_at  = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    avg_dmg_share = Column(Float, default=0.20)        # part des dégâts de l'équipe (0.0–1.0)

    __table_args__ = (
        UniqueConstraint("champion", "tier", "lane", "region", name="uq_champ_stats"),
        Index("idx_champ_stats_lookup", "champion", "tier", "region"),
    )