"""Modèles Affaire et AffaireItem."""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from ..database import Base


class Affaire(Base):
    __tablename__ = "affaires"

    id              = Column(String, primary_key=True, index=True)
    num_affaire     = Column(String, nullable=False, unique=True, index=True)
    client_id       = Column(String, ForeignKey("clients.id"), index=True)
    nom_projet      = Column(String, default="")
    navire_machine  = Column(String, default="")
    ref_interne     = Column(String, default="")
    charge_affaire  = Column(String, default="")
    date_debut      = Column(String, default="")   # JJ/MM/AAAA
    date_fin_prevue = Column(String, default="")   # JJ/MM/AAAA
    date_cloture    = Column(String, default="")   # JJ/MM/AAAA
    statut          = Column(String, default="En cours", index=True)
    description     = Column(String, default="")
    commentaires    = Column(String, default="")
    dossier_path    = Column(String, default="")
    version         = Column(Integer, default=1)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), server_default=func.now(),
                             onupdate=func.now())

    client = relationship("Client", backref="affaires")
    items  = relationship("AffaireItem", back_populates="affaire",
                          cascade="all, delete-orphan",
                          order_by="AffaireItem.ordre")


class AffaireItem(Base):
    __tablename__ = "affaire_items"

    id          = Column(String, primary_key=True, index=True)
    affaire_id  = Column(String, ForeignKey("affaires.id"), index=True)
    type_item   = Column(String, default="")   # Moteur principal, Inverseur/Réducteur, ...
    libelle     = Column(String, default="")   # Nom libre / désignation
    marque      = Column(String, default="")
    reference   = Column(String, default="")
    num_serie   = Column(String, default="")
    objectif    = Column(String, default="")   # Ce qui doit être fait/livré
    suivi       = Column(String, default="")   # Notes de suivi
    statut      = Column(String, default="À faire")  # À faire / En cours / Terminé / NC
    details_json = Column(String, default="{}")  # Champs spécifiques au type
    ordre       = Column(Integer, default=0)
    version     = Column(Integer, default=1)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), server_default=func.now(),
                         onupdate=func.now())

    affaire = relationship("Affaire", back_populates="items")
