from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class LootBoxType(Base):
    __tablename__ = "lootbox_types"

    id              = Column(Integer, primary_key=True)
    name            = Column(String(100), nullable=False)
    description     = Column(String(200), nullable=True)
    image_url       = Column(String, nullable=True)
    price_coins     = Column(Integer, nullable=True)              # NULL = pas achetable
    pool_types      = Column(String(200), nullable=False)
    collection_filter = Column(String(500), nullable=True)  # CSV des collections, NULL = toutes      # CSV: "champion,sticker,..."
    drop_common     = Column(Integer, nullable=False, default=60)
    drop_rare       = Column(Integer, nullable=False, default=25)
    drop_epic       = Column(Integer, nullable=False, default=12)
    drop_legendary  = Column(Integer, nullable=False, default=3)
    is_active       = Column(Boolean, nullable=False, default=True)
    created_at      = Column(TIMESTAMP, server_default=func.now())


class LootBox(Base):
    __tablename__ = "lootboxes"

    id              = Column(Integer, primary_key=True)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False)
    box_type_id     = Column(Integer, ForeignKey("lootbox_types.id"), nullable=False)
    obtained_at     = Column(TIMESTAMP, server_default=func.now())
    opened_at       = Column(TIMESTAMP, nullable=True)
    opened_card_id  = Column(Integer, ForeignKey("cards.id"), nullable=True)

    box_type    = relationship("LootBoxType", lazy="joined")
    opened_card = relationship("Card", lazy="joined")