"""Schémas Pydantic – Intervention."""
from __future__ import annotations
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel
 
 
class InterventionCreate(BaseModel):
    num_bon:                str = ""          # vide = auto-généré par le router
    client_id:              Optional[str] = None
    moteur_id:              Optional[str] = None
    type_intervention:      str = ""
    urgence:                str = "Normale"
    statut:                 str = "En cours"
    technicien:             str = ""
    date_creation:          str = ""
    date_cloture:           str = ""
    lieu_intervention:      str = ""
    nom_signataire:         str = ""
    email_signataire:       str = ""
    nb_heures_fct:          str = ""
    num_commande_client:    str = ""
    # Classifications
    garantie_intervention:  int = 0
    facturable:             int = 0
    interne:                int = 0
    # Options
    outil_diagnostic:       int = 0
    memoriser_avant:        int = 0
    memoriser_apres:        int = 0
    photos_avant:           int = 0
    photos_apres:           int = 0
    pour_information:       int = 0
    preconisation:          int = 0
    # Textes
    demande_client:         str = ""
    constat:                str = ""
    travaux:                str = ""
    informations:           str = ""
    preconisation_text:     str = ""
    description:            str = ""
    pieces:                 str = ""
    # JSON
    materiels_json:         str = "[]"
    deplacements_json:      str = "{}"
    dossier_path:           str = ""
    # Notifications
    client_notifie:         int = 0
    tech_notifie:           int = 0
    # Signatures
    signature_b64:          str = ""
    signature_nom:          str = ""
    signature_date:         str = ""
    signature_tech_b64:     str = ""
    signature_tech_nom:     str = ""
    signature_tech_date:    str = ""
 
 
class InterventionUpdate(BaseModel):
    num_bon:                Optional[str] = None
    client_id:              Optional[str] = None
    moteur_id:              Optional[str] = None
    type_intervention:      Optional[str] = None
    urgence:                Optional[str] = None
    statut:                 Optional[str] = None
    technicien:             Optional[str] = None
    date_creation:          Optional[str] = None
    date_cloture:           Optional[str] = None
    lieu_intervention:      Optional[str] = None
    nom_signataire:         Optional[str] = None
    email_signataire:       Optional[str] = None
    nb_heures_fct:          Optional[str] = None
    num_commande_client:    Optional[str] = None
    garantie_intervention:  Optional[int] = None
    facturable:             Optional[int] = None
    interne:                Optional[int] = None
    outil_diagnostic:       Optional[int] = None
    memoriser_avant:        Optional[int] = None
    memoriser_apres:        Optional[int] = None
    photos_avant:           Optional[int] = None
    photos_apres:           Optional[int] = None
    pour_information:       Optional[int] = None
    preconisation:          Optional[int] = None
    demande_client:         Optional[str] = None
    constat:                Optional[str] = None
    travaux:                Optional[str] = None
    informations:           Optional[str] = None
    preconisation_text:     Optional[str] = None
    description:            Optional[str] = None
    pieces:                 Optional[str] = None
    materiels_json:         Optional[str] = None
    deplacements_json:      Optional[str] = None
    dossier_path:           Optional[str] = None
    client_notifie:         Optional[int] = None
    tech_notifie:           Optional[int] = None
    signature_b64:          Optional[str] = None
    signature_nom:          Optional[str] = None
    signature_date:         Optional[str] = None
    signature_tech_b64:     Optional[str] = None
    signature_tech_nom:     Optional[str] = None
    signature_tech_date:    Optional[str] = None
 
 
class InterventionOut(BaseModel):
    id:                     str
    num_bon:                str
    client_id:              Optional[str] = None
    moteur_id:              Optional[str] = None
    # Champs enrichis (ajoutés par _to_out dans le router)
    # Champs enrichis (ajoutés par _to_out dans le router)
    client_nom:             Optional[str] = None
    moteur_serie:           Optional[str] = None
    # Champs additionnels utilisés par le code Tkinter
    navire:                 str = ""
    num_serie:              str = ""
    marque:                 str = ""
    type_intervention:      str
    urgence:                str
    statut:                 str
    technicien:             str
    date_creation:          str
    date_cloture:           str = ""
    lieu_intervention:      str
    nom_signataire:         str
    email_signataire:       str
    nb_heures_fct:          str
    num_commande_client:    str = ""
    garantie_intervention:  int
    facturable:             int
    interne:                int
    outil_diagnostic:       int
    memoriser_avant:        int
    memoriser_apres:        int
    photos_avant:           int
    photos_apres:           int
    pour_information:       int
    preconisation:          int
    demande_client:         str
    constat:                str
    travaux:                str
    informations:           str
    preconisation_text:     str
    description:            str
    pieces:                 str
    materiels_json:         str
    deplacements_json:      str
    dossier_path:           str
    client_notifie:         int
    tech_notifie:           int
    signature_b64:          str
    signature_nom:          str
    signature_date:         str
    signature_tech_b64:     str
    signature_tech_nom:     str
    signature_tech_date:    str
    version:                int = 1
    sync_state:             str = "atelier"
    sync_device:            str = ""
    sync_checkout_at:       str = ""
    created_at:             Optional[datetime] = None
    updated_at:             Optional[datetime] = None
 
    model_config = {"from_attributes": True}
 
 
class SignatureIn(BaseModel):
    """Payload pour POST /interventions/{id}/signature."""
    role:           Literal["client", "technicien"] = "client"
    signature_b64:  str = ""
    signature_nom:  str = ""