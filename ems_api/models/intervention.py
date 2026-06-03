"""Modèle Intervention (le plus complet : bons + signatures + synchro)."""
from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from ..database import Base


class Intervention(Base):
    __tablename__ = "interventions"

    id                    = Column(String, primary_key=True, index=True)
    num_bon               = Column(String, nullable=False, unique=True, index=True)
    client_id             = Column(String, ForeignKey("clients.id"), index=True)
    moteur_id             = Column(String, ForeignKey("moteurs.id"), index=True)
    type_intervention     = Column(String, default="")
    urgence               = Column(String, default="Normale")
    statut                = Column(String, default="En cours", index=True)
    technicien            = Column(String, default="")          # CSV multi-tech
    date_creation         = Column(String, default="")          # JJ/MM/AAAA
    date_cloture          = Column(String, default="")          # JJ/MM/AAAA
    lieu_intervention     = Column(String, default="")
    nom_signataire        = Column(String, default="")
    email_signataire      = Column(String, default="")
    telephone_signataire = Column(String, default="")
    nom_demandeur     = Column(String, default="")
    email_demandeur   = Column(String, default="")
    telephone_demandeur = Column(String, default="")
    nb_heures_fct         = Column(String, default="")
    num_commande_client   = Column(String, default="")

    # Classifications
    garantie_intervention = Column(Integer, default=0)
    facturable            = Column(Integer, default=0)
    interne               = Column(Integer, default=0)

    # Options
    outil_diagnostic      = Column(Integer, default=0)
    memoriser_avant       = Column(Integer, default=0)
    memoriser_apres       = Column(Integer, default=0)
    photos_avant          = Column(Integer, default=0)
    photos_apres          = Column(Integer, default=0)
    pour_information      = Column(Integer, default=0)
    preconisation         = Column(Integer, default=0)

    # Textes
    demande_client        = Column(String, default="")
    constat               = Column(String, default="")
    travaux               = Column(String, default="")
    informations          = Column(String, default="")
    preconisation_text    = Column(String, default="")
    description           = Column(String, default="")
    pieces                = Column(String, default="")

    # JSON brut
    materiels_json        = Column(String, default="[]")
    deplacements_json     = Column(String, default="{}")
    dossier_path          = Column(String, default="")

    # Notifications
    client_notifie        = Column(Integer, default=0)
    tech_notifie          = Column(Integer, default=0)

    # Signatures
    signature_b64         = Column(String, default="")
    signature_nom         = Column(String, default="")
    signature_date        = Column(String, default="")
    signature_tech_b64    = Column(String, default="")
    signature_tech_nom    = Column(String, default="")
    signature_tech_date   = Column(String, default="")

    # Synchronisation tournee terrain
    version          = Column(Integer, default=1)        # incremente a chaque modif
    sync_state       = Column(String, default="atelier") # "atelier" ou "terrain"
    sync_device      = Column(String, default="")        # ex: "tablette-1"
    sync_checkout_at = Column(String, default="")        # date de depart en tournee

    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True),
                          server_default=func.now(),
                          onupdate=func.now())

    client = relationship("Client", back_populates="interventions")
    moteur = relationship("Moteur", back_populates="interventions")
