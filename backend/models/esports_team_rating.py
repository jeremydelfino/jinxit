from sqlalchemy import Column, Integer, String, Float, Text, Boolean
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.sql import func
from database import Base

class EsportsTeamRating(Base):
    __tablename__ = "esports_team_ratings"

    id            = Column(Integer, primary_key=True)
    team_code     = Column(String(20), unique=True, nullable=False, index=True)
    manual_boost  = Column(Float, default=1.0)
    notes         = Column(Text, nullable=True)
    is_active     = Column(Boolean, default=True)
    updated_at    = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())