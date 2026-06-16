"""Modèle Moteur."""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from ..database import Base


class Moteur(Base):
    __tablename__ = "moteurs"

    id                  = Column(String, primary_key=True, index=True)
    client_id           = Column(String, ForeignKey("clients.id"), index=True)
    num_serie           = Column(String, nullable=False, unique=True, index=True)
    navire              = Column(String, default="")
    machine             = Column(String, default="")
    type_moteur         = Column(String, default="")
    marque              = Column(String, default="")
    famille             = Column(String, default="")
    cylindree           = Column(String, default="")
    application         = Column(String, default="")
    typologie           = Column(String, default="")
    collection          = Column(String, default="")
    ref_constructeur    = Column(String, default="")
    code_affaire        = Column(String, default="")
    type_client                 = Column(String, default="")
    date_mise_service           = Column(String, default="")   # JJ/MM/AAAA
    duree_garantie              = Column(String, default="")   # ex. "24" (mois)
    client_utilisateur_nom      = Column(String, default="")
    client_utilisateur_email    = Column(String, default="")
    client_utilisateur_tel      = Column(String, default="")
    client_utilisateur_adresse  = Column(String, default="")
    version             = Column(Integer, default=1)
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    updated_at          = Column(DateTime(timezone=True), server_default=func.now(),
                                  onupdate=func.now())

    client          = relationship("Client", back_populates="moteurs")
    interventions   = relationship("Intervention", back_populates="moteur")
    garanties       = relationship("Garantie", back_populates="moteur",
                                    cascade="all, delete-orphan")
    sous_ensembles  = relationship("SousEnsemble", back_populates="moteur",
                                    cascade="all, delete-orphan",
                                    order_by="SousEnsemble.libelle")
