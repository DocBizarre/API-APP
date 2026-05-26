"""Schemas Pydantic - Amelioration."""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class AmeliorationCreate(BaseModel):
    num_ticket:     str = ""
    titre:          str = ""
    client_id:      Optional[str] = None
    description:    str = ""
    priorite:       str = "Moyenne"
    statut:         str = "Nouveau"
    technicien:     str = ""
    date_cible:     str = ""
    commentaires:   str = ""
    dossier_path:   str = ""


class AmeliorationUpdate(BaseModel):
    num_ticket:     Optional[str] = None
    titre:          Optional[str] = None
    client_id:      Optional[str] = None
    description:    Optional[str] = None
    priorite:       Optional[str] = None
    statut:         Optional[str] = None
    technicien:     Optional[str] = None
    date_cible:     Optional[str] = None
    commentaires:   Optional[str] = None
    dossier_path:   Optional[str] = None


class AmeliorationOut(BaseModel):
    id:             str
    num_ticket:     str
    titre:          str
    client_id:      Optional[str] = None
    description:    str
    priorite:       str
    statut:         str
    technicien:     str = ""
    date_cible:     str = ""
    commentaires:   str
    dossier_path:   str
    # Champ enrichi (ajoute par _to_out dans le router)
    client_nom:     Optional[str] = ""
    created_at:     Optional[datetime] = None
    updated_at:     Optional[datetime] = None

    model_config = {"from_attributes": True}
