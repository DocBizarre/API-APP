"""Schémas Pydantic – Fournisseur (base fournisseurs des achats)."""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, field_validator


def _strip(v):
    return v.strip() if isinstance(v, str) else v


class FournisseurCreate(BaseModel):
    nom:         str
    contact:     str = ""
    email:       str = ""
    telephone:   str = ""
    rue:         str = ""
    code_postal: str = ""
    ville:       str = ""
    pays:        str = ""

    @field_validator("*", mode="before")
    @classmethod
    def _strip_all(cls, v):
        return _strip(v)


class FournisseurUpdate(BaseModel):
    nom:         Optional[str] = None
    contact:     Optional[str] = None
    email:       Optional[str] = None
    telephone:   Optional[str] = None
    rue:         Optional[str] = None
    code_postal: Optional[str] = None
    ville:       Optional[str] = None
    pays:        Optional[str] = None

    @field_validator("*", mode="before")
    @classmethod
    def _strip_all(cls, v):
        return _strip(v)


class FournisseurOut(BaseModel):
    id:          str
    nom:         str
    contact:     str = ""
    email:       str = ""
    telephone:   str = ""
    rue:         str = ""
    code_postal: str = ""
    ville:       str = ""
    pays:        str = ""
    usage_count: int = 1
    nb_references: int = 0     # références produits liées (table piece_fournisseurs)

    model_config = {"from_attributes": True}
