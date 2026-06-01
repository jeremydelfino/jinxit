from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.sql import func
from database import Base


class GmContract(Base):
    __tablename__ = "gm_contracts"

    id          = Column(Integer, primary_key=True)
    team_id     = Column(Integer, ForeignKey("gm_teams.id", ondelete="CASCADE"), nullable=False)
    card_id     = Column(Integer, ForeignKey("gm_player_cards.id"), nullable=False)
    role_slot   = Column(String(10), nullable=True)        # rôle joué (def = card.role)
    salary      = Column(Integer, nullable=False)          # figé à l'acquisition
    side        = Column(String(8), nullable=False, default="NEUTRAL")  # STRONG/WEAK/NEUTRAL
    is_starter  = Column(Boolean, nullable=False, default=False)
    acquired_at = Column(TIMESTAMP, server_default=func.now())