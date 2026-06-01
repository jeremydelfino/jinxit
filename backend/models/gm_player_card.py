from sqlalchemy import Column, Integer, SmallInteger, String, Boolean, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP, JSONB
from sqlalchemy.sql import func
from database import Base


class GmPlayerCard(Base):
    __tablename__ = "gm_player_cards"

    id                = Column(Integer, primary_key=True)
    esports_player_id = Column(Integer, ForeignKey("esports_players.id"), nullable=True)  # NULL = carte fictive/event
    variant           = Column(String(20), nullable=False, default="BASE")
    role              = Column(String(10), nullable=False)   # TOP/JUNGLE/MID/ADC/SUPPORT (normalisé)
    nationality       = Column(String(2), nullable=True)     # ISO-2, pour l'algo synergie/langue

    # ── Stats mécaniques 0-100 ──
    laning    = Column(SmallInteger, nullable=False, default=70)
    teamfight = Column(SmallInteger, nullable=False, default=70)
    vision    = Column(SmallInteger, nullable=False, default=70)
    mechanics = Column(SmallInteger, nullable=False, default=70)
    # ── Mental ──
    stress    = Column(SmallInteger, nullable=False, default=70)   # 0-100 (bas = instable)
    clutch    = Column(SmallInteger, nullable=False, default=70)   # 0-100
    ego       = Column(SmallInteger, nullable=False, default=3)    # 1-5 (étoiles)

    traits      = Column(JSONB, nullable=False, default=list)      # ["VETERAN","FRANCHISE",...]
    ovr         = Column(SmallInteger, nullable=False, default=0)  # caché, dérivé des 6 stats
    base_salary = Column(Integer, nullable=False, default=0)
    photo_url   = Column(String, nullable=True)   # override admin (prioritaire sur esports_player.photo_url)       # /journée, dérivé de l'ovr
    is_active   = Column(Boolean, nullable=False, default=True)
    created_at  = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("esports_player_id", "variant", name="uq_card_player_variant"),
        CheckConstraint("ego BETWEEN 1 AND 5", name="ck_card_ego"),
    )