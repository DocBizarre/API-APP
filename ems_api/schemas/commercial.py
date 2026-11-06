"""Schémas Pydantic – Commercial (commerciaux EMS des affaires)."""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, field_validator


def _strip(v):
    return v.strip() if isinstance(v, str) else v


class CommercialCreate(BaseModel):
    nom:       str
    email:     str = ""
    telephone: str = ""

    @field_validator("*", mode="before")
    @classmethod
    def _strip_all(cls, v):
        return _strip(v)


class CommercialUpdate(BaseModel):
    nom:       Optional[str] = None
    email:     Optional[str] = None
    telephone: Optional[str] = None

    @field_validator("*", mode="before")
    @classmethod
    def _strip_all(cls, v):
        return _strip(v)


class CommercialOut(BaseModel):
    id:          str
    nom:         str
    email:       str = ""
    telephone:   str = ""
    usage_count: int = 0
    nb_affaires: int = 0
