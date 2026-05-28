"""Modèle Piece (pièces détachées en stock)."""
from sqlalchemy import Column, String, Integer, DateTime, func
from ..database import Base


class Piece(Base):
    __tablename__ = "pieces"

    id         = Column(String, primary_key=True, index=True)
    reference  = Column(String, nullable=False, unique=True, index=True)
    libelle    = Column(String, default="", index=True)
    marque     = Column(String, default="", index=True)
    notes      = Column(String, default="")

    version    = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True),
                         server_default=func.now(),
                         onupdate=func.now())
