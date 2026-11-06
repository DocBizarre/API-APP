"""Modèles IntentionAchat et IntentionAchatLigne (intentions d'achat / confirmations
préliminaires envoyées à un fournisseur, distinctes des bons de commande engageants)."""
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from ..database import Base


class IntentionAchat(Base):
    __tablename__ = "intentions_achat"

    id                      = Column(String, primary_key=True, index=True)
    affaire_id              = Column(String, ForeignKey("affaires.id"), index=True)
    num_ia                  = Column(String, nullable=False, unique=True, index=True)
    langue                  = Column(String, default="fr")  # "fr" ou "en" — langue du PDF généré
    reference_devis         = Column(String, default="")   # référence du devis EMS
    reference_client        = Column(String, default="")   # référence / n° de commande côté client
    fournisseur_nom         = Column(String, default="")
    reference_fournisseur   = Column(String, default="")
    reference_monstock      = Column(String, default="")
    lien_monstock           = Column(String, default="")
    fournisseur_rue         = Column(String, default="")
    fournisseur_code_postal = Column(String, default="")
    fournisseur_ville       = Column(String, default="")
    fournisseur_pays        = Column(String, default="France")
    fournisseur_contact     = Column(String, default="")
    fournisseur_email       = Column(String, default="")
    fournisseur_tel         = Column(String, default="")
    interlocuteurs_fournisseur = Column(String, default="[]")  # JSON : liste de contacts côté fournisseur
    livraison_nom           = Column(String, default="")
    livraison_rue           = Column(String, default="")
    livraison_code_postal   = Column(String, default="")
    livraison_ville         = Column(String, default="")
    livraison_pays          = Column(String, default="France")
    incoterm                = Column(String, default="")
    lieu_livraison_texte    = Column(String, default="")   # ex. "FCA Gainsborough UK"
    delai_livraison_texte   = Column(String, default="")   # ex. "6-64 weeks after PO"
    conditions_paiement_texte = Column(String, default="")  # ex. "30% down payment / 60% ..."
    garantie_texte          = Column(String, default="")   # ex. "24 months warranty from delivery"
    charge_commande_nom     = Column(String, default="")
    charge_commande_email   = Column(String, default="")
    charge_commande_tel     = Column(String, default="")
    date_commande           = Column(String, default="")   # JJ/MM/AAAA
    date_livraison_prevue   = Column(String, default="")   # JJ/MM/AAAA
    date_livraison_reelle   = Column(String, default="")   # JJ/MM/AAAA
    date_reglement          = Column(String, default="")   # JJ/MM/AAAA — vide = non réglé
    statut                  = Column(String, default="Brouillon", index=True)
    conditions              = Column(String, default="")
    notes                   = Column(String, default="")
    exonere_tva             = Column(Integer, default=0)
    frais_port              = Column(Float, default=0.0)
    date_generation         = Column(DateTime(timezone=True))
    pdf_path                = Column(String, default="")
    # Envoi au fournisseur (renseigné depuis l'app Affaire après l'envoi du mail)
    envoye_le               = Column(String, default="")   # JJ/MM/AAAA HH:MM, vide = non envoyé
    envoye_a                = Column(String, default="")   # destinataire(s)
    version                 = Column(Integer, default=1)
    created_at              = Column(DateTime(timezone=True), server_default=func.now())
    updated_at              = Column(DateTime(timezone=True), server_default=func.now(),
                                     onupdate=func.now())

    affaire = relationship("Affaire", backref="intentions_achat")
    lignes  = relationship("IntentionAchatLigne", back_populates="intention_achat",
                           cascade="all, delete-orphan",
                           order_by="IntentionAchatLigne.ordre")


class IntentionAchatLigne(Base):
    __tablename__ = "intentions_achat_lignes"

    id                = Column(String, primary_key=True, index=True)
    intention_achat_id = Column(String, ForeignKey("intentions_achat.id"), index=True)
    piece_id          = Column(String, ForeignKey("pieces.id"), nullable=True, index=True)
    reference         = Column(String, default="")   # P/N
    drawing_no        = Column(String, default="")
    libelle           = Column(String, default="")   # description
    ratio_notes       = Column(String, default="")
    quantite          = Column(Float, default=1.0)
    prix_unitaire     = Column(Float, default=0.0)
    montant_ligne      = Column(Float, default=0.0)
    ordre             = Column(Integer, default=0)
    created_at        = Column(DateTime(timezone=True), server_default=func.now())
    updated_at        = Column(DateTime(timezone=True), server_default=func.now(),
                                onupdate=func.now())

    intention_achat = relationship("IntentionAchat", back_populates="lignes")
    piece           = relationship("Piece")
