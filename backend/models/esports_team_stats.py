from sqlalchemy import Column, Integer, String, Float
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.sql import func
from database import Base

class EsportsTeamStats(Base):
    __tablename__ = "esports_team_stats"

    id            = Column(Integer, primary_key=True)
    team_code     = Column(String(20), nullable=False, index=True)
    team_name     = Column(String(100), nullable=True)
    team_image    = Column(String, nullable=True)
    league_slug   = Column(String(50), nullable=False)
    tournament_id = Column(String(100), nullable=True)
    wins          = Column(Integer, default=0)
    losses        = Column(Integer, default=0)
    winrate       = Column(Float, default=0.5)
    updated_at    = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())