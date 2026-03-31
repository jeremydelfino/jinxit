from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.dialects.postgresql import TIMESTAMP, JSONB
from sqlalchemy.sql import func
from database import Base

class LiveGame(Base):
    __tablename__ = "live_games"

    id                  = Column(Integer, primary_key=True)
    searched_player_id  = Column(Integer, ForeignKey("searched_players.id"), nullable=False)
    riot_game_id        = Column(String(100), unique=True, nullable=False)
    queue_type          = Column(String(50), nullable=True)
    blue_team           = Column(JSONB, nullable=False)
    red_team            = Column(JSONB, nullable=False)
    duration_seconds    = Column(Integer, default=0)
    status              = Column(String(20), default="live")
    fetched_at          = Column(TIMESTAMP, server_default=func.now())
    odds_data           = Column(JSONB, nullable=True)
    region              = Column(String(10), nullable=True)