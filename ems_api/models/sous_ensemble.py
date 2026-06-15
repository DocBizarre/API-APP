"""Modèle SousEnsemble — composant rattaché à un moteur du parc."""
from sqlalchemy import Column, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from ..database import Base


class SousEnsemble(Base):
    __tablename__ = "sous_ensembles"

    id          = Column(String, primary_key=True, index=True)
    moteur_id   = Column(String, ForeignKey("moteurs.id", ondelete="CASCADE"), nullable=False, index=True)
    libelle     = Column(String, nullable=False)
    reference   = Column(String, default="")
    marque      = Column(String, default="")
    num_serie   = Column(String, default="")
    etat        = Column(String, default="")   # Neuf / Bon état / Usagé / Hors service
    notes       = Column(String, default="")
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    moteur = relationship("Moteur", back_populates="sous_ensembles")
