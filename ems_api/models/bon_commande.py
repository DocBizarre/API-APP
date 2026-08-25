"""Modèles BonCommande et BonCommandeLigne (achats fournisseur liés à une affaire)."""
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from ..database import Base


class BonCommande(Base):
    __tablename__ = "bons_commande"

    id                      = Column(String, primary_key=True, index=True)
    affaire_id              = Column(String, ForeignKey("affaires.id"), index=True)
    num_bc                  = Column(String, nullable=False, unique=True, index=True)
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
    frais_port              = Column(Float, default=0.0)  # frais de port HT, distincts des lignes/pièces
    chapitre_cout           = Column(String, default="")  # chapitre de coût du bilan affaire (vide = non affecté)
    paiements               = Column(String, default="[]")  # échéancier de paiement (JSON)
    date_generation         = Column(DateTime(timezone=True))
    pdf_path                = Column(String, default="")
    version                 = Column(Integer, default=1)
    created_at              = Column(DateTime(timezone=True), server_default=func.now())
    updated_at              = Column(DateTime(timezone=True), server_default=func.now(),
                                     onupdate=func.now())

    affaire = relationship("Affaire", backref="bons_commande")
    lignes  = relationship("BonCommandeLigne", back_populates="bon_commande",
                           cascade="all, delete-orphan",
                           order_by="BonCommandeLigne.ordre")


class BonCommandeLigne(Base):
    __tablename__ = "bons_commande_lignes"

    id               = Column(String, primary_key=True, index=True)
    bon_commande_id  = Column(String, ForeignKey("bons_commande.id"), index=True)
    piece_id         = Column(String, ForeignKey("pieces.id"), nullable=True, index=True)
    reference        = Column(String, default="")
    libelle          = Column(String, default="")
    quantite         = Column(Float, default=1.0)
    prix_unitaire    = Column(Float, default=0.0)
    montant_ligne    = Column(Float, default=0.0)
    ordre            = Column(Integer, default=0)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())
    updated_at       = Column(DateTime(timezone=True), server_default=func.now(),
                              onupdate=func.now())

    bon_commande = relationship("BonCommande", back_populates="lignes")
    piece        = relationship("Piece")
