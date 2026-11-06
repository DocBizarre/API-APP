"""Modèles ReceptionAchat et ReceptionAchatLigne : réceptions (éventuellement
partielles) des articles d'un bon de commande fournisseur.

Une réception = une livraison physique (un bon de livraison fournisseur). Elle
porte, pour chaque ligne du BC livrée, la quantité reçue ce jour-là ; la
quantité reçue d'une ligne est la somme de ses lignes de réception.
"""
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from ..database import Base


class ReceptionAchat(Base):
    __tablename__ = "receptions_achat"

    id               = Column(String, primary_key=True, index=True)
    bon_commande_id  = Column(String, ForeignKey("bons_commande.id"), index=True)
    date_reception   = Column(String, default="")   # JJ/MM/AAAA
    numero_bl        = Column(String, default="")   # n° du bon de livraison fournisseur
    receptionnaire   = Column(String, default="")
    commentaire      = Column(String, default="")
    created_at       = Column(DateTime(timezone=True), server_default=func.now())

    bon_commande = relationship("BonCommande", back_populates="receptions")
    lignes       = relationship("ReceptionAchatLigne", back_populates="reception",
                                cascade="all, delete-orphan")


class ReceptionAchatLigne(Base):
    __tablename__ = "receptions_achat_lignes"

    id                    = Column(String, primary_key=True, index=True)
    reception_id          = Column(String, ForeignKey("receptions_achat.id"), index=True)
    # Pas de clé étrangère : la ligne du BC peut être supprimée ensuite, la
    # réception reste dans l'historique (référence / désignation recopiées).
    bon_commande_ligne_id = Column(String, index=True)
    reference             = Column(String, default="")
    libelle               = Column(String, default="")
    quantite_recue        = Column(Float, default=0.0)

    reception = relationship("ReceptionAchat", back_populates="lignes")
