"""Schémas Pydantic – Piece."""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class PieceCreate(BaseModel):
    reference:  str
    libelle:    str = ""
    marque:     str = ""
    notes:      str = ""
    prix_achat: float = 0
    prix_vente: float = 0
    # Optionnels (import / ajout depuis un achat) : lie la pièce à ce fournisseur
    fournisseur:     str = ""
    ref_fournisseur: str = ""


PIECE_LINK_FIELDS = {"fournisseur", "ref_fournisseur"}   # hors colonnes de la table pieces


class PieceFournisseurIn(BaseModel):
    """Lien pièce ↔ fournisseur saisi à la main (app Parc)."""
    fournisseur_nom: str
    ref_fournisseur: str = ""
    prix_achat:      float = 0


class PieceUpdate(BaseModel):
    reference:  Optional[str] = None
    libelle:    Optional[str] = None
    marque:     Optional[str] = None
    notes:      Optional[str] = None
    prix_achat: Optional[float] = None
    prix_vente: Optional[float] = None


class PieceOut(BaseModel):
    id:         str
    reference:  str
    libelle:    str
    marque:     str
    notes:      str
    prix_achat: float = 0
    prix_vente: float = 0
    version:    int = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Fournisseurs liés : [{fournisseur_id, nom, ref_fournisseur, prix_achat, date_dernier_achat}]
    fournisseurs:     list[dict] = []
    # Renseignés quand la liste est demandée pour un fournisseur précis (?fournisseur=)
    chez_fournisseur: bool = False
    prix_fournisseur: Optional[float] = None
    ref_fournisseur:  str = ""

    model_config = {"from_attributes": True}


class PieceBulkImport(BaseModel):
    """Pour l'import en masse depuis CSV/Excel."""
    pieces: list[PieceCreate]
    skip_doublons: bool = True   # ignorer les références déjà en base
    fournisseur: str = ""        # fournisseur par défaut des lignes qui n'en précisent pas
    dry_run: bool = False        # simulation : calcule le résultat sans rien écrire


class PieceImportResult(BaseModel):
    """Résultat d'un import en masse."""
    importees: int      # nouvelles pièces ajoutées
    mises_a_jour: int   # pièces existantes mises à jour
    ignorees: int       # doublons ignorés
    completees: int = 0  # doublons ignorés mais complétés (champs vides remplis)
    erreurs: int        # lignes invalides
    details_erreurs: list[str] = []
