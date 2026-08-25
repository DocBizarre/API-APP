"""Schemas Pydantic Moteur."""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class MoteurCreate(BaseModel):
    client_id:          str
    num_serie:          str
    parent_moteur_id:   Optional[str] = None
    navire:             str = ""
    navire_immatriculation: str = ""
    navire_port_attache:    str = ""
    machine:            str = ""
    marque:             str = ""
    type_moteur:        str = ""
    application:        str = ""
    typologie:          str = ""
    puissance_rpm:      str = ""
    puissance_pme_rpm:  str = ""
    ref_constructeur:   str = ""
    code_affaire:                str = ""
    type_client:                 str = ""
    date_mise_service:           str = ""
    duree_garantie:              str = ""
    client_utilisateur_nom:      str = ""
    client_utilisateur_email:    str = ""
    client_utilisateur_tel:      str = ""
    client_utilisateur_adresse:  str = ""


class MoteurUpdate(BaseModel):
    client_id:          Optional[str] = None
    num_serie:          Optional[str] = None
    parent_moteur_id:   Optional[str] = None
    navire:             Optional[str] = None
    navire_immatriculation: Optional[str] = None
    navire_port_attache:    Optional[str] = None
    machine:            Optional[str] = None
    marque:             Optional[str] = None
    type_moteur:        Optional[str] = None
    application:        Optional[str] = None
    typologie:          Optional[str] = None
    puissance_rpm:      Optional[str] = None
    puissance_pme_rpm:  Optional[str] = None
    ref_constructeur:   Optional[str] = None
    code_affaire:                Optional[str] = None
    type_client:                 Optional[str] = None
    date_mise_service:           Optional[str] = None
    duree_garantie:              Optional[str] = None
    client_utilisateur_nom:      Optional[str] = None
    client_utilisateur_email:    Optional[str] = None
    client_utilisateur_tel:      Optional[str] = None
    client_utilisateur_adresse:  Optional[str] = None


class MoteurOut(BaseModel):
    id:                 str
    client_id:          Optional[str] = None
    parent_moteur_id:   Optional[str] = None
    num_serie:          str
    navire:             str
    navire_immatriculation: str = ""
    navire_port_attache:    str = ""
    machine:            str
    marque:             str
    type_moteur:        str
    application:        str
    typologie:          str
    puissance_rpm:      str = ""
    puissance_pme_rpm:  str = ""
    ref_constructeur:   str
    code_affaire:                str
    type_client:                 str
    date_mise_service:           str
    duree_garantie:              str
    client_utilisateur_nom:      str = ""
    client_utilisateur_email:    str = ""
    client_utilisateur_tel:      str = ""
    client_utilisateur_adresse:  str = ""
    # Champs enrichis (ajoutés par _to_out dans le router)
    client_nom:           Optional[str] = ""
    nb_sous_ensembles:    int = 0
    affaire_liee:         bool = False
    version:              int = 1
    created_at:           Optional[datetime] = None
    updated_at:           Optional[datetime] = None

    model_config = {"from_attributes": True}
