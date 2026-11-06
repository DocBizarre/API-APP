"""Lien références produits ↔ fournisseurs (plusieurs fournisseurs possibles
par référence). Alimenté automatiquement par les bons de commande et
intentions d'achat, par l'import CSV du catalogue, et gérable dans l'app Parc."""
from sqlalchemy import Column, String, Float, ForeignKey, UniqueConstraint
from ..database import Base


class PieceFournisseur(Base):
    __tablename__ = "piece_fournisseurs"
    __table_args__ = (UniqueConstraint("piece_id", "fournisseur_id",
                                       name="uq_piece_fournisseur"),)

    id              = Column(String, primary_key=True, index=True)
    piece_id        = Column(String, ForeignKey("pieces.id"), nullable=False, index=True)
    fournisseur_id  = Column(String, ForeignKey("fournisseurs.id"), nullable=False, index=True)
    ref_fournisseur = Column(String, default="")   # référence chez ce fournisseur
    prix_achat      = Column(Float, default=0.0)   # dernier prix d'achat HT connu
    date_dernier_achat = Column(String, default="")  # JJ/MM/AAAA (dernier BC / IA)
