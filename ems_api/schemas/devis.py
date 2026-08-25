"""Schemas Pydantic - Devis & DevisLigne."""
from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class DevisLigneIn(BaseModel):
    piece_id:      Optional[str] = None
    reference:     str = ""
    libelle:       str = ""
    quantite:      float = 1.0
    prix_unitaire: float = 0.0
    remise_pct:    float = 0.0
    ordre:         int = 0


class DevisLigneOut(BaseModel):
    id:            str
    devis_id:      str
    piece_id:      Optional[str] = None
    reference:     str = ""
    libelle:       str = ""
    quantite:      float = 1.0
    prix_unitaire: float = 0.0
    remise_pct:    float = 0.0
    montant_ligne: float = 0.0
    ordre:         int = 0
    created_at:    Optional[datetime] = None
    updated_at:    Optional[datetime] = None

    model_config = {"from_attributes": True}


class DevisCreate(BaseModel):
    client_id:              str
    moteur_id:              Optional[str] = None
    objet:                  str = ""
    description:            str = ""
    demande_client:          str = ""
    date_devis:             str = ""
    date_validite:          str = ""
    statut:                 str = "Brouillon"
    navire_nom:              str = ""
    navire_immatriculation:  str = ""
    navire_pavillon:         str = ""
    navire_port_attache:     str = ""
    navire_type_usage:       str = ""
    lieu_intervention:       str = ""
    destinataire_nom:        str = ""
    destinataire_email:      str = ""
    destinataire_telephone:  str = ""
    acompte_pct:             float = 30.0
    delai_paiement_jours:    int = 30
    conditions:     str = ""
    notes:          str = ""
    exonere_tva:    int = 0
    moteurs_supplementaires_json: str = "[]"
    lignes:         List[DevisLigneIn] = []


class DevisUpdate(BaseModel):
    client_id:      Optional[str] = None
    moteur_id:      Optional[str] = None
    objet:          Optional[str] = None
    description:    Optional[str] = None
    demande_client: Optional[str] = None
    date_devis:     Optional[str] = None
    date_validite:  Optional[str] = None
    statut:         Optional[str] = None
    navire_nom:              Optional[str] = None
    navire_immatriculation:  Optional[str] = None
    navire_pavillon:         Optional[str] = None
    navire_port_attache:     Optional[str] = None
    navire_type_usage:       Optional[str] = None
    lieu_intervention:       Optional[str] = None
    destinataire_nom:        Optional[str] = None
    destinataire_email:      Optional[str] = None
    destinataire_telephone:  Optional[str] = None
    acompte_pct:             Optional[float] = None
    delai_paiement_jours:    Optional[int] = None
    conditions:     Optional[str] = None
    notes:          Optional[str] = None
    exonere_tva:    Optional[int] = None
    moteurs_supplementaires_json: Optional[str] = None
    lignes:         Optional[List[DevisLigneIn]] = None


class DevisOut(BaseModel):
    id:                    str
    client_id:             str = ""
    client_nom:            Optional[str] = None
    moteur_id:             Optional[str] = None
    moteur_num_serie:      Optional[str] = None
    num_devis:             str
    objet:                 str = ""
    description:           str = ""
    demande_client:         str = ""
    date_devis:            str = ""
    date_validite:         str = ""
    statut:                str = "Brouillon"
    navire_nom:              str = ""
    navire_immatriculation:  str = ""
    navire_pavillon:         str = ""
    navire_port_attache:     str = ""
    navire_type_usage:       str = ""
    lieu_intervention:       str = ""
    destinataire_nom:        str = ""
    destinataire_email:      str = ""
    destinataire_telephone:  str = ""
    acompte_pct:             float = 30.0
    delai_paiement_jours:    int = 30
    conditions:            str = ""
    notes:                 str = ""
    exonere_tva:           int = 0
    moteurs_supplementaires_json: str = "[]"
    intervention_id:       Optional[str] = None
    intervention_num_bon:  Optional[str] = None
    date_generation:       Optional[datetime] = None
    pdf_path:              str = ""
    version:               int = 1
    lignes:                List[DevisLigneOut] = []
    total_lignes_ht:       float = 0
    total_ht:               float = 0
    total_ttc:              float = 0
    created_at:            Optional[datetime] = None
    updated_at:            Optional[datetime] = None

    model_config = {"from_attributes": True}


class DevisTransformOut(BaseModel):
    devis:           DevisOut
    intervention_id: str
    num_bon:         str
