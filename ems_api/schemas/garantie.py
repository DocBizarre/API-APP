"""Schemas Pydantic - Garantie."""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class GarantieCreate(BaseModel):
    num_ems:            str = ""
    num_constructeur:   str = ""
    moteur_id:          Optional[str] = None
    client_id:          Optional[str] = None
    intervention_id:    Optional[str] = None
    attribution:        str = "Constructeur"
    statut:             str = "Suivi EMS"
    responsable:        str = ""
    nom_demandeur:      str = ""
    email_demandeur:    str = ""
    telephone_demandeur: str = ""
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
    intervention_id:    Optional[str] = None
    attribution:        Optional[str] = None
    statut:             Optional[str] = None
    responsable:        Optional[str] = None
    nom_demandeur:      Optional[str] = None
    email_demandeur:    Optional[str] = None
    telephone_demandeur: Optional[str] = None
    date_ouverture:     Optional[str] = None
    date_cloture:       Optional[str] = None
    montant:            Optional[str] = None
    description:        Optional[str] = None
    commentaires:       Optional[str] = None
    dossier_path:       Optional[str] = None
    client_notifie:     Optional[int] = None
    tech_notifie:       Optional[int] = None


class GarantieOut(BaseModel):
    id:                 str
    num_ems:            str
    num_constructeur:   str
    moteur_id:          Optional[str] = None
    client_id:          Optional[str] = None
    intervention_id:    Optional[str] = None
    attribution:        str
    statut:             str
    responsable:        str = ""
    nom_demandeur:      str = ""
    email_demandeur:    str = ""
    telephone_demandeur: str = ""
    date_ouverture:     str
    date_cloture:       str
    montant:            str
    description:        str
    commentaires:       str
    dossier_path:       str
    client_notifie:     int = 0
    tech_notifie:       int = 0
    # Champs enrichis (ajoutes par _to_out dans le router)
    client_nom:         Optional[str] = ""
    intervention_num_bon: Optional[str] = ""
    moteur_serie:       Optional[str] = ""
    num_serie:          Optional[str] = ""    # alias de moteur_serie
    marque:             Optional[str] = ""
    moteur_marque:      Optional[str] = ""
    version:         int = 1
    created_at:         Optional[datetime] = None
    updated_at:         Optional[datetime] = None

    model_config = {"from_attributes": True}
