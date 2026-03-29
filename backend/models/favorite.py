from sqlalchemy import Column, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.sql import func
from database import Base

class UserFavorite(Base):
    __tablename__ = "user_favorites"

    id              = Column(Integer, primary_key=True)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False)
    riot_player_id  = Column(Integer, ForeignKey("searched_players.id"), nullable=False)
    created_at      = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "riot_player_id", name="uq_user_favorite"),
    )