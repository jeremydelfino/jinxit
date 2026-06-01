from sqlalchemy import Column, Integer, BigInteger, SmallInteger, String, ForeignKey
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.sql import func
from database import Base


class GmTeam(Base):
    __tablename__ = "gm_teams"

    id          = Column(Integer, primary_key=True)
    owner_id    = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)  # 1 save / user
    name        = Column(String(60), nullable=False)
    logo_url    = Column(String, nullable=True)
    league      = Column(String(10), nullable=False, default="LFL")
    budget      = Column(BigInteger, nullable=False, default=0)
    fans        = Column(Integer, nullable=False, default=0)
    reputation  = Column(SmallInteger, nullable=False, default=50)   # 0-100
    ovr_cached  = Column(SmallInteger, nullable=False, default=0)
    created_at  = Column(TIMESTAMP, server_default=func.now())