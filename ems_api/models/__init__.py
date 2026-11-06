"""Importer ce module charge tous les modèles SQLAlchemy d'un coup."""
from .client import Client
from .moteur import Moteur
from .intervention import Intervention
from .garantie import Garantie
from .amelioration import Amelioration
from .technicien import Technicien
from .configurations import TypeIntervention, StatutGarantie, Config
from .piece import Piece
from .affaire import Affaire, AffaireItem
from .contact import Contact
from .bon_commande import BonCommande, BonCommandeLigne
from .reception_achat import ReceptionAchat, ReceptionAchatLigne
from .fournisseur import Fournisseur
from .commercial import Commercial
from .piece_fournisseur import PieceFournisseur
from .devis import Devis, DevisLigne
from .navire import Navire

__all__ = ["Client", "Moteur", "Intervention",
           "Garantie", "Amelioration", "Technicien",
           "TypeIntervention", "StatutGarantie", "Config",
           "Piece", "Affaire", "AffaireItem", "Contact",
           "BonCommande", "BonCommandeLigne", "ReceptionAchat", "ReceptionAchatLigne",
           "Fournisseur", "Commercial", "PieceFournisseur",
           "Devis", "DevisLigne", "Navire"]
