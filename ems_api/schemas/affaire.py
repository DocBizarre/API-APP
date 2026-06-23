"""Schemas Pydantic - Affaire & AffaireItem."""
from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class AffaireItemCreate(BaseModel):
    type_item:    str = ""
    libelle:      str = ""
    marque:       str = ""
    reference:    str = ""
    num_serie:    str = ""
    objectif:     str = ""
    suivi:        str = ""
    statut:       str = "À faire"
    details_json: str = "{}"
    ordre:        int = 0


class AffaireItemUpdate(BaseModel):
    type_item:    Optional[str] = None
    libelle:      Optional[str] = None
    marque:       Optional[str] = None
    reference:    Optional[str] = None
    num_serie:    Optional[str] = None
    objectif:     Optional[str] = None
    suivi:        Optional[str] = None
    statut:       Optional[str] = None
    details_json: Optional[str] = None
    ordre:        Optional[int] = None


class AffaireItemOut(BaseModel):
    id:           str
    affaire_id:   str
    type_item:    str
    libelle:      str
    marque:       str
    reference:    str
    num_serie:    str
    objectif:     str
    suivi:        str
    statut:       str
    details_json: str
    dossier_path: str = ""
    ordre:        int
    created_at:   Optional[datetime] = None
    updated_at:   Optional[datetime] = None

    model_config = {"from_attributes": True}


class AffaireCreate(BaseModel):
    num_affaire:             str = ""
    client_id:               Optional[str] = None
    nom_projet:              str = ""
    navire_machine:          str = ""
    ref_interne:             str = ""
    num_commande_client:     str = ""
    charge_affaire:          str = ""
    date_debut:              str = ""
    date_fin_prevue:         str = ""
    date_cloture:            str = ""
    statut:                  str = "En cours"
    description:             str = ""
    commentaires:            str = ""
    dossier_path:            str = ""
    prix_ht:                 str = ""
    exonere_tva:             int = 0
    date_achat:              str = ""
    fournisseur:             str = ""
    etablissement_financier: str = ""
    echeances_facturation:   str = "[]"
    whiteboard:              str = ""
    transporteur:            str = ""
    contact_transport:       str = ""
    prix_transport:          str = ""
    num_suivi_transport:     str = ""
    instructions_transport:  str = ""


class AffaireUpdate(BaseModel):
    client_id:               Optional[str] = None
    nom_projet:              Optional[str] = None
    navire_machine:          Optional[str] = None
    ref_interne:             Optional[str] = None
    num_commande_client:     Optional[str] = None
    charge_affaire:          Optional[str] = None
    date_debut:              Optional[str] = None
    date_fin_prevue:         Optional[str] = None
    date_cloture:            Optional[str] = None
    statut:                  Optional[str] = None
    description:             Optional[str] = None
    commentaires:            Optional[str] = None
    dossier_path:            Optional[str] = None
    prix_ht:                 Optional[str] = None
    exonere_tva:             Optional[int] = None
    date_achat:              Optional[str] = None
    fournisseur:             Optional[str] = None
    etablissement_financier: Optional[str] = None
    echeances_facturation:   Optional[str] = None
    whiteboard:              Optional[str] = None
    transporteur:            Optional[str] = None
    contact_transport:       Optional[str] = None
    prix_transport:          Optional[str] = None
    num_suivi_transport:     Optional[str] = None
    instructions_transport:  Optional[str] = None


class AffaireOut(BaseModel):
    id:                      str
    num_affaire:             str
    client_id:               Optional[str] = None
    nom_projet:              str
    navire_machine:          str
    ref_interne:             str
    num_commande_client:     str = ""
    charge_affaire:          str
    date_debut:              str
    date_fin_prevue:         str
    date_cloture:            str
    statut:                  str
    description:             str
    commentaires:            str
    dossier_path:            str
    prix_ht:                 str = ""
    exonere_tva:             int = 0
    date_achat:              str = ""
    fournisseur:             str = ""
    etablissement_financier: str = ""
    echeances_facturation:   str = "[]"
    whiteboard:              str = ""
    transporteur:            str = ""
    contact_transport:       str = ""
    prix_transport:          str = ""
    num_suivi_transport:     str = ""
    instructions_transport:  str = ""
    client_nom:              Optional[str] = ""
    nb_items:                int = 0
    created_at:              Optional[datetime] = None
    updated_at:              Optional[datetime] = None

    model_config = {"from_attributes": True}
