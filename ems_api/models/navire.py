"""Modèle Navire (registre auto-alimenté, sur le modèle de Fournisseur)."""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from ..database import Base


class Navire(Base):
    __tablename__ = "navires"

    id               = Column(String, primary_key=True, index=True)
    nom              = Column(String, nullable=False, unique=True, index=True)
    immatriculation  = Column(String, default="")
    port_attache     = Column(String, default="")
    proprietaire_id  = Column(String, ForeignKey("clients.id"), nullable=True, index=True)
    usage_count      = Column(Integer, default=1)
    version          = Column(Integer, default=1)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())
    updated_at       = Column(DateTime(timezone=True), server_default=func.now(),
                              onupdate=func.now())

    proprietaire = relationship("Client", backref="navires")
