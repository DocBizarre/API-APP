"""Schémas Pydantic – Contact (signataires / demandeurs)."""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, field_validator

from ..services.phone import format_telephone


class ContactCreate(BaseModel):
    nom:         str
    email:       str = ""
    telephone:   str = ""
    entreprise:  str = ""

    @field_validator("telephone")
    @classmethod
    def _format_telephone(cls, v: str) -> str:
        return format_telephone(v)


class ContactUpdate(BaseModel):
    nom:         Optional[str] = None
    email:       Optional[str] = None
    telephone:   Optional[str] = None
    entreprise:  Optional[str] = None

    @field_validator("telephone")
    @classmethod
    def _format_telephone(cls, v: Optional[str]) -> Optional[str]:
        return None if v is None else format_telephone(v)


class ContactOut(BaseModel):
    id:          str
    nom:         str
    email:       str
    telephone:   str
    entreprise:  str = ""
    usage_count: int = 1

    model_config = {"from_attributes": True}
