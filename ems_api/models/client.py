"""Modèle Client."""
from sqlalchemy import Column, String, DateTime, func
from sqlalchemy.orm import relationship
from ..database import Base


class Client(Base):
    __tablename__ = "clients"

    id          = Column(String, primary_key=True, index=True)
    nom         = Column(String, nullable=False, unique=True, index=True)
    contact     = Column(String, default="")
    email       = Column(String, default="")
    telephone   = Column(String, default="")
    adresse     = Column(String, default="")
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), server_default=func.now(),
                          onupdate=func.now())

    moteurs        = relationship("Moteur", back_populates="client",
                                   cascade="all, delete-orphan")
    interventions  = relationship("Intervention", back_populates="client")
    garanties      = relationship("Garantie", back_populates="client")
    ameliorations  = relationship("Amelioration", back_populates="client")
