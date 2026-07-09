"""Schemas Pydantic - BonCommande & BonCommandeLigne."""
from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class BonCommandeLigneIn(BaseModel):
    piece_id:      Optional[str] = None
    reference:     str = ""
    libelle:       str = ""
    quantite:      float = 1.0
    prix_unitaire: float = 0.0
    ordre:         int = 0


class BonCommandeLigneOut(BaseModel):
    id:            str
    bon_commande_id: str
    piece_id:      Optional[str] = None
    reference:     str = ""
    libelle:       str = ""
    quantite:      float = 1.0
    prix_unitaire: float = 0.0
    montant_ligne: float = 0.0
    ordre:         int = 0
    created_at:    Optional[datetime] = None
    updated_at:    Optional[datetime] = None

    model_config = {"from_attributes": True}


class BonCommandeCreate(BaseModel):
    affaire_id:            Optional[str] = None
    fournisseur_nom:       str = ""
    fournisseur_adresse:   str = ""
    fournisseur_contact:   str = ""
    fournisseur_email:     str = ""
    fournisseur_tel:       str = ""
    date_commande:         str = ""
    date_livraison_prevue: str = ""
    date_livraison_reelle: str = ""
    date_reglement:        str = ""
    statut:                str = "Brouillon"
    conditions:            str = ""
    notes:                 str = ""
    exonere_tva:           int = 0
    lignes:                List[BonCommandeLigneIn] = []


class BonCommandeUpdate(BaseModel):
    affaire_id:            Optional[str] = None
    fournisseur_nom:       Optional[str] = None
    fournisseur_adresse:   Optional[str] = None
    fournisseur_contact:   Optional[str] = None
    fournisseur_email:     Optional[str] = None
    fournisseur_tel:       Optional[str] = None
    date_commande:         Optional[str] = None
    date_livraison_prevue: Optional[str] = None
    date_livraison_reelle: Optional[str] = None
    date_reglement:        Optional[str] = None
    statut:                Optional[str] = None
    conditions:            Optional[str] = None
    notes:                 Optional[str] = None
    exonere_tva:           Optional[int] = None
    lignes:                Optional[List[BonCommandeLigneIn]] = None


class BonCommandeOut(BaseModel):
    id:                    str
    affaire_id:            Optional[str] = None
    affaire_num:           Optional[str] = None
    affaire_nom:           Optional[str] = None
    num_bc:                str
    fournisseur_nom:       str = ""
    fournisseur_adresse:   str = ""
    fournisseur_contact:   str = ""
    fournisseur_email:     str = ""
    fournisseur_tel:       str = ""
    date_commande:         str = ""
    date_livraison_prevue: str = ""
    date_livraison_reelle: str = ""
    date_reglement:        str = ""
    statut:                str = "Brouillon"
    conditions:            str = ""
    notes:                 str = ""
    exonere_tva:           int = 0
    date_generation:       Optional[datetime] = None
    pdf_path:              str = ""
    version:               int = 1
    lignes:                List[BonCommandeLigneOut] = []
    total_ht:              float = 0
    total_ttc:             float = 0
    created_at:            Optional[datetime] = None
    updated_at:            Optional[datetime] = None

    model_config = {"from_attributes": True}
