from sqlalchemy import Column, Integer, SmallInteger, String, Boolean
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.sql import func
from database import Base


class GmPackType(Base):
    __tablename__ = "gm_pack_types"

    id            = Column(Integer, primary_key=True)
    name          = Column(String(80), nullable=False)
    description   = Column(String, nullable=True)
    image_url     = Column(String, nullable=True)
    price_budget  = Column(Integer, nullable=False)

    # ── Poids par tranche d'OVR (Σ = 100) ──
    w_70_74 = Column(SmallInteger, nullable=False, default=0)
    w_75_84 = Column(SmallInteger, nullable=False, default=0)
    w_85_89 = Column(SmallInteger, nullable=False, default=0)
    w_90_99 = Column(SmallInteger, nullable=False, default=0)

    league_filter = Column(String(10), nullable=True)   # ex: 'LFL' (= esports_players.region)
    role_filter   = Column(String(10), nullable=True)
    is_active     = Column(Boolean, nullable=False, default=True)
    created_at    = Column(TIMESTAMP, server_default=func.now())