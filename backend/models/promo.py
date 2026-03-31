from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class PromoCode(Base):
    __tablename__ = "promo_codes"

    id            = Column(Integer, primary_key=True)
    code          = Column(String(50), unique=True, nullable=False)   # ex: "JUNGLEGAP2026"
    description   = Column(String(200), nullable=True)                # label admin
    coins_amount  = Column(Integer, default=0)                        # 0 = pas de coins
    card_id       = Column(Integer, ForeignKey("cards.id"), nullable=True)  # null = pas de carte
    max_uses      = Column(Integer, nullable=True)                    # null = illimité au total
    uses_count    = Column(Integer, default=0)
    is_active     = Column(Boolean, default=True)
    created_at    = Column(TIMESTAMP, server_default=func.now())

    card  = relationship("Card", lazy="joined")
    uses  = relationship("PromoCodeUse", back_populates="promo_code", cascade="all, delete-orphan")


class PromoCodeUse(Base):
    __tablename__ = "promo_code_uses"

    id            = Column(Integer, primary_key=True)
    promo_code_id = Column(Integer, ForeignKey("promo_codes.id"), nullable=False)
    user_id       = Column(Integer, ForeignKey("users.id"), nullable=False)
    used_at       = Column(TIMESTAMP, server_default=func.now())

    promo_code = relationship("PromoCode", back_populates="uses")