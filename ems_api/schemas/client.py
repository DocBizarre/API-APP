"""Schémas Pydantic – Client."""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
 
 
# ── Création ────────────────────────────────────────────────────────────────
class ClientCreate(BaseModel):
    nom:        str
    contact:    str = ""
    email:      str = ""
    telephone:  str = ""
    adresse:    str = ""
 
 
# ── Mise à jour partielle (tous les champs optionnels) ───────────────────────
class ClientUpdate(BaseModel):
    nom:        Optional[str] = None
    contact:    Optional[str] = None
    email:      Optional[str] = None
    telephone:  Optional[str] = None
    adresse:    Optional[str] = None
 
 
# ── Réponse API ──────────────────────────────────────────────────────────────
class ClientOut(BaseModel):
    id:         str
    nom:        str
    contact:    str
    email:      str
    telephone:  str
    adresse:    str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
 
    model_config = {"from_attributes": True}