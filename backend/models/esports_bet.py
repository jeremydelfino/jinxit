from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.sql import func
from database import Base


class EsportsBet(Base):
    __tablename__ = "esports_bets"

    id              = Column(Integer, primary_key=True)
    user_id         = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Identifiant du match LoL Esports (match_id de l'API)
    match_id        = Column(String(100), nullable=False, index=True)

    # Infos du match snapshot au moment du pari
    league_slug     = Column(String(50), nullable=True)
    league_name     = Column(String(100), nullable=True)
    team1_code      = Column(String(20), nullable=True)
    team2_code      = Column(String(20), nullable=True)
    team1_name      = Column(String(100), nullable=True)
    team2_name      = Column(String(100), nullable=True)
    team1_image     = Column(String, nullable=True)
    team2_image     = Column(String, nullable=True)
    bo_format       = Column(Integer, default=3)          # 1, 3 ou 5

    # Ce sur quoi on parie
    # bet_type: "match_winner" | "exact_score"
    bet_type        = Column(String(50), nullable=False)
    # bet_value pour match_winner: "team1" | "team2"
    # bet_value pour exact_score: "team1_2-0" | "team1_2-1" | "team2_2-0" | etc.
    bet_value       = Column(String(50), nullable=False)

    amount          = Column(Integer, nullable=False)
    odds            = Column(Float, nullable=False)        # cote au moment du pari
    payout          = Column(Integer, nullable=True)

    # "pending" | "won" | "lost" | "cancelled"
    status          = Column(String(20), default="pending")

    # Résultat réel du match (rempli à la résolution)
    actual_winner   = Column(String(20), nullable=True)   # "team1" | "team2"
    actual_score    = Column(String(20), nullable=True)   # "2-0", "2-1", etc.

    match_start_time = Column(TIMESTAMP, nullable=True)
    created_at      = Column(TIMESTAMP, server_default=func.now())
    resolved_at     = Column(TIMESTAMP, nullable=True)