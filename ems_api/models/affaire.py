"""Modèles Affaire et AffaireItem."""
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from ..database import Base


class Affaire(Base):
    __tablename__ = "affaires"

    id              = Column(String, primary_key=True, index=True)
    num_affaire     = Column(String, nullable=False, unique=True, index=True)
    complexite      = Column(String, default="")   # A / B / C
    client_id       = Column(String, ForeignKey("clients.id"), index=True)
    nom_projet      = Column(String, default="")
    navire_machine  = Column(String, default="")
    navire_immatriculation = Column(String, default="")
    navire_port_attache    = Column(String, default="")
    ref_interne            = Column(String, default="")
    num_commande_client    = Column(String, default="")
    charge_affaire         = Column(String, default="")
    resp_technique         = Column(String, default="")
    commercial             = Column(String, default="")   # commercial EMS en charge de l'affaire
    commercial_email       = Column(String, default="")
    commercial_tel         = Column(String, default="")
    date_debut      = Column(String, default="")   # JJ/MM/AAAA
    date_fat        = Column(String, default="")   # JJ/MM/AAAA — début FAT (Factory Acceptance Test)
    date_fin_fat    = Column(String, default="")   # JJ/MM/AAAA — fin FAT
    date_fin_prevue = Column(String, default="")   # JJ/MM/AAAA
    date_cloture    = Column(String, default="")   # JJ/MM/AAAA
    date_visite_appli_debut  = Column(String, default="")   # JJ/MM/AAAA — début visite applicative
    date_visite_appli_fin    = Column(String, default="")   # JJ/MM/AAAA — fin visite applicative
    date_commissioning_debut = Column(String, default="")   # JJ/MM/AAAA — début commissioning
    date_commissioning_fin   = Column(String, default="")   # JJ/MM/AAAA — fin commissioning
    statut          = Column(String, default="En cours", index=True)
    description     = Column(String, default="")
    commentaires    = Column(String, default="")
    dossier_path             = Column(String, default="")
    prix_ht                  = Column(String, default="")
    exonere_tva              = Column(Integer, default=0)
    date_achat               = Column(String, default="")   # JJ/MM/AAAA
    fournisseur              = Column(String, default="")
    reference_fournisseur    = Column(String, default="")
    etablissement_financier  = Column(String, default="")
    echeances_facturation    = Column(String, default="[]")
    lots_vendus               = Column(String, default="[]")  # lots vendus, chacun avec son propre échéancier
    whiteboard               = Column(String, default="")
    transporteur             = Column(String, default="")
    contact_transport        = Column(String, default="")
    prix_transport           = Column(String, default="")
    num_suivi_transport      = Column(String, default="")
    instructions_transport   = Column(String, default="")
    livraison_nom            = Column(String, default="")
    livraison_rue            = Column(String, default="")
    livraison_code_postal    = Column(String, default="")
    livraison_ville          = Column(String, default="")
    livraison_pays           = Column(String, default="France")
    conditions_reglement     = Column(String, default="")
    garanties                = Column(String, default="")
    interlocuteurs_client    = Column(String, default="[]")
    version         = Column(Integer, default=1)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), server_default=func.now(),
                             onupdate=func.now())

    client = relationship("Client", backref="affaires")
    items  = relationship("AffaireItem", back_populates="affaire",
                          cascade="all, delete-orphan",
                          order_by="AffaireItem.ordre")
    couts  = relationship("AffaireCoutLigne", back_populates="affaire",
                          cascade="all, delete-orphan",
                          order_by="AffaireCoutLigne.ordre")


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
    dossier_path = Column(String, default="")   # Sous-dossier dédié au chapitre
    ordre       = Column(Integer, default=0)
    version     = Column(Integer, default=1)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), server_default=func.now(),
                         onupdate=func.now())

    affaire = relationship("Affaire", back_populates="items")


class AffaireCoutLigne(Base):
    """Ligne de bilan : un poste de coût prévu (devis) vs coût réel constaté."""
    __tablename__ = "affaire_couts"

    id           = Column(String, primary_key=True, index=True)
    affaire_id   = Column(String, ForeignKey("affaires.id"), index=True)
    categorie    = Column(String, default="")   # Chapitre de coût (liste fixe côté UI)
    libelle      = Column(String, default="")
    cout_prevu   = Column(Float, default=0.0)   # montant si stade P1 (prévisionnel)
    cout_reel    = Column(Float, default=0.0)   # montant si stade P2 (coût réel)
    stade        = Column(String, default="P1")  # P1 = prévisionnel initial, P2 = coût réel
    bon_commande_id = Column(String, ForeignKey("bons_commande.id"), nullable=True, index=True)
    poste_lie_id = Column(String, ForeignKey("affaire_couts.id"), nullable=True, index=True)  # poste P1 associé (pour un poste P2)
    commentaire  = Column(String, default="")
    ordre        = Column(Integer, default=0)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    updated_at   = Column(DateTime(timezone=True), server_default=func.now(),
                          onupdate=func.now())

    affaire = relationship("Affaire", back_populates="couts")
