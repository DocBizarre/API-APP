"""Modèle Garantie."""
from sqlalchemy import Column, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from ..database import Base


class Garantie(Base):
    __tablename__ = "garanties"

    id                  = Column(String, primary_key=True, index=True)
    num_ems             = Column(String, nullable=False, unique=True, index=True)
    num_constructeur    = Column(String, default="")
    moteur_id           = Column(String, ForeignKey("moteurs.id"), index=True)
    client_id           = Column(String, ForeignKey("clients.id"), index=True)
    attribution         = Column(String, default="Constructeur")  # Constructeur / EMS
    statut              = Column(String, default="Suivi EMS", index=True)
    date_ouverture      = Column(String, default="")   # JJ/MM/AAAA
    date_cloture        = Column(String, default="")   # JJ/MM/AAAA
    montant             = Column(String, default="")
    description         = Column(String, default="")
    commentaires        = Column(String, default="")
    dossier_path        = Column(String, default="")
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    updated_at          = Column(DateTime(timezone=True), server_default=func.now(),
                                  onupdate=func.now())

    client = relationship("Client", back_populates="garanties")
    moteur = relationship("Moteur", back_populates="garanties")
