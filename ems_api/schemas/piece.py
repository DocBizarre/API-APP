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


class PieceUpdate(BaseModel):
    reference:  Optional[str] = None
    libelle:    Optional[str] = None
    marque:     Optional[str] = None
    notes:      Optional[str] = None


class PieceOut(BaseModel):
    id:         str
    reference:  str
    libelle:    str
    marque:     str
    notes:      str
    version:    int = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PieceBulkImport(BaseModel):
    """Pour l'import en masse depuis CSV/Excel."""
    pieces: list[PieceCreate]
    skip_doublons: bool = True   # ignorer les références déjà en base


class PieceImportResult(BaseModel):
    """Résultat d'un import en masse."""
    importees: int      # nouvelles pièces ajoutées
    mises_a_jour: int   # pièces existantes mises à jour
    ignorees: int       # doublons ignorés
    erreurs: int        # lignes invalides
    details_erreurs: list[str] = []
