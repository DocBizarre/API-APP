"""Schémas Pydantic – Navire."""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# ── Création ────────────────────────────────────────────────────────────────
class NavireCreate(BaseModel):
    nom:             str
    immatriculation: str = ""
    port_attache:    str = ""
    proprietaire_id: Optional[str] = None


# ── Mise à jour partielle (tous les champs optionnels) ───────────────────────
class NavireUpdate(BaseModel):
    nom:             Optional[str] = None
    immatriculation: Optional[str] = None
    port_attache:    Optional[str] = None
    proprietaire_id: Optional[str] = None


# ── Réponse API ──────────────────────────────────────────────────────────────
class NavireOut(BaseModel):
    id:               str
    nom:              str
    immatriculation:  str
    port_attache:     str
    proprietaire_id:  Optional[str] = None
    proprietaire_nom: str = ""
    usage_count:      int = 1
    version:          int = 1
    created_at:       Optional[datetime] = None
    updated_at:       Optional[datetime] = None

    model_config = {"from_attributes": True}
