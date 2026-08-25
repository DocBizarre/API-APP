"""Modèles Devis et DevisLigne (devis chiffrés client, transformables en bon d'intervention)."""
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from ..database import Base


class Devis(Base):
    __tablename__ = "devis"

    id                      = Column(String, primary_key=True, index=True)
    num_devis               = Column(String, nullable=False, unique=True, index=True)
    client_id               = Column(String, ForeignKey("clients.id"), index=True)
    moteur_id               = Column(String, ForeignKey("moteurs.id"), nullable=True, index=True)
    objet                   = Column(String, default="")
    description              = Column(String, default="")
    demande_client            = Column(String, default="")
    date_devis               = Column(String, default="")   # JJ/MM/AAAA
    date_validite            = Column(String, default="")   # JJ/MM/AAAA
    statut                   = Column(String, default="Brouillon", index=True)
    navire_nom               = Column(String, default="")
    navire_immatriculation   = Column(String, default="")   # n° francisation
    navire_pavillon          = Column(String, default="")
    navire_port_attache      = Column(String, default="")
    navire_type_usage        = Column(String, default="")   # commerce, pêche, servitude…
    lieu_intervention        = Column(String, default="")
    destinataire_nom         = Column(String, default="")
    destinataire_email       = Column(String, default="")
    destinataire_telephone   = Column(String, default="")
    acompte_pct              = Column(Float, default=30.0)
    delai_paiement_jours     = Column(Integer, default=30)
    conditions                = Column(String, default="")
    notes                     = Column(String, default="")
    exonere_tva               = Column(Integer, default=0)
    moteurs_supplementaires_json = Column(String, default="[]")
    intervention_id           = Column(String, ForeignKey("interventions.id"), nullable=True, index=True)
    pdf_path                  = Column(String, default="")
    date_generation            = Column(DateTime(timezone=True))
    version                    = Column(Integer, default=1)
    created_at                 = Column(DateTime(timezone=True), server_default=func.now())
    updated_at                 = Column(DateTime(timezone=True), server_default=func.now(),
                                        onupdate=func.now())

    client       = relationship("Client")
    moteur       = relationship("Moteur")
    intervention = relationship("Intervention", back_populates="devis")
    lignes       = relationship("DevisLigne", back_populates="devis",
                                cascade="all, delete-orphan",
                                order_by="DevisLigne.ordre")


class DevisLigne(Base):
    __tablename__ = "devis_lignes"

    id             = Column(String, primary_key=True, index=True)
    devis_id       = Column(String, ForeignKey("devis.id"), index=True)
    piece_id       = Column(String, ForeignKey("pieces.id"), nullable=True, index=True)
    reference      = Column(String, default="")
    libelle        = Column(String, default="")
    quantite       = Column(Float, default=1.0)
    prix_unitaire  = Column(Float, default=0.0)
    remise_pct     = Column(Float, default=0.0)
    montant_ligne  = Column(Float, default=0.0)
    ordre          = Column(Integer, default=0)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
    updated_at     = Column(DateTime(timezone=True), server_default=func.now(),
                            onupdate=func.now())

    devis = relationship("Devis", back_populates="lignes")
    piece = relationship("Piece")
