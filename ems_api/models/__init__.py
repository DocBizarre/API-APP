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
from .sous_ensemble import SousEnsemble

__all__ = ["Client", "Moteur", "Intervention",
           "Garantie", "Amelioration", "Technicien",
           "TypeIntervention", "StatutGarantie", "Config",
           "Piece", "Affaire", "AffaireItem", "SousEnsemble"]
