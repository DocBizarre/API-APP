"""Schémas Pydantic – Garantie."""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
 
 
class GarantieCreate(BaseModel):
    num_ems:            str
    num_constructeur:   str = ""
    moteur_id:          Optional[str] = None
    client_id:          Optional[str] = None
    attribution:        str = "Constructeur"
    statut:             str = "Suivi EMS"
    date_ouverture:     str = ""
    date_cloture:       str = ""
    montant:            str = ""
    description:        str = ""
    commentaires:       str = ""
    dossier_path:       str = ""
 
 
class GarantieUpdate(BaseModel):
    num_ems:            Optional[str] = None
    num_constructeur:   Optional[str] = None
    moteur_id:          Optional[str] = None
    client_id:          Optional[str] = None
    attribution:        Optional[str] = None
    statut:             Optional[str] = None
    date_ouverture:     Optional[str] = None
    date_cloture:       Optional[str] = None
    montant:            Optional[str] = None
    description:        Optional[str] = None
    commentaires:       Optional[str] = None
    dossier_path:       Optional[str] = None
 
 
class GarantieOut(BaseModel):
    id:                 str
    num_ems:            str
    num_constructeur:   str
    moteur_id:          Optional[str] = None
    client_id:          Optional[str] = None
    attribution:        str
    statut:             str
    date_ouverture:     str
    date_cloture:       str
    montant:            str
    description:        str
    commentaires:       str
    dossier_path:       str
    created_at:         Optional[datetime] = None
    updated_at:         Optional[datetime] = None
 
    model_config = {"from_attributes": True}