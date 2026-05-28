from sqlalchemy import Column, Integer, Boolean, ForeignKey, String, CheckConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class UserCard(Base):
    __tablename__ = "user_cards"

    id             = Column(Integer, primary_key=True)
    user_id        = Column(Integer, ForeignKey("users.id"), nullable=False)
    card_id        = Column(Integer, ForeignKey("cards.id"), nullable=False)
    equipped       = Column(Boolean, default=False)
    quantity       = Column(Integer, nullable=False, default=1)
    equipped_slot  = Column(String(10), nullable=True)
    obtained_at    = Column(TIMESTAMP, server_default=func.now())
    position_x = Column(Integer, nullable=True)
    position_y = Column(Integer, nullable=True)
    size = Column(String(10), default="medium")

    card = relationship("Card")

    __table_args__ = (
        CheckConstraint(
            "equipped_slot IS NULL OR equipped_slot IN ('left', 'center', 'right')",
            name="user_cards_equipped_slot_check"
        ),
    )