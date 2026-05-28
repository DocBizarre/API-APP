"""Modèle Technicien."""
from sqlalchemy import Column, String, Integer, DateTime, func
from ..database import Base


class Technicien(Base):
    __tablename__ = "techniciens"

    id          = Column(String, primary_key=True, index=True)
    nom         = Column(String, nullable=False, unique=True, index=True)
    email       = Column(String, default="")
    telephone   = Column(String, default="")
    version     = Column(Integer, default=1)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), server_default=func.now(),
                          onupdate=func.now())
