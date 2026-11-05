"""Schemas Pydantic - IntentionAchat & IntentionAchatLigne."""
from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class IntentionAchatLigneIn(BaseModel):
    piece_id:      Optional[str] = None
    reference:     str = ""
    drawing_no:    str = ""
    libelle:       str = ""
    ratio_notes:   str = ""
    quantite:      float = 1.0
    prix_unitaire: float = 0.0
    ordre:         int = 0


class IntentionAchatLigneOut(BaseModel):
    id:                 str
    intention_achat_id: str
    piece_id:           Optional[str] = None
    reference:          str = ""
    drawing_no:         str = ""
    libelle:            str = ""
    ratio_notes:        str = ""
    quantite:           float = 1.0
    prix_unitaire:      float = 0.0
    montant_ligne:      float = 0.0
    ordre:              int = 0
    created_at:         Optional[datetime] = None
    updated_at:         Optional[datetime] = None

    model_config = {"from_attributes": True}


class IntentionAchatCreate(BaseModel):
    affaire_id:            Optional[str] = None
    langue:                str = "fr"
    reference_devis:       str = ""
    reference_client:      str = ""
    fournisseur_nom:       str = ""
    reference_fournisseur:   str = ""
    reference_monstock:      str = ""
    lien_monstock:           str = ""
    fournisseur_rue:         str = ""
    fournisseur_code_postal: str = ""
    fournisseur_ville:       str = ""
    fournisseur_pays:        str = "France"
    fournisseur_contact:   str = ""
    fournisseur_email:     str = ""
    fournisseur_tel:       str = ""
    interlocuteurs_fournisseur: str = "[]"
    livraison_nom:         str = ""
    livraison_rue:         str = ""
    livraison_code_postal: str = ""
    livraison_ville:       str = ""
    livraison_pays:        str = "France"
    incoterm:              str = ""
    lieu_livraison_texte:  str = ""
    delai_livraison_texte: str = ""
    conditions_paiement_texte: str = ""
    garantie_texte:        str = ""
    charge_commande_nom:   str = ""
    charge_commande_email: str = ""
    charge_commande_tel:   str = ""
    date_commande:         str = ""
    date_livraison_prevue: str = ""
    date_livraison_reelle: str = ""
    date_reglement:        str = ""
    statut:                str = "Brouillon"
    conditions:            str = ""
    notes:                 str = ""
    exonere_tva:           int = 0
    frais_port:            float = 0.0
    lignes:                List[IntentionAchatLigneIn] = []


class IntentionAchatUpdate(BaseModel):
    affaire_id:            Optional[str] = None
    langue:                Optional[str] = None
    reference_devis:       Optional[str] = None
    reference_client:      Optional[str] = None
    fournisseur_nom:       Optional[str] = None
    reference_fournisseur:   Optional[str] = None
    reference_monstock:      Optional[str] = None
    lien_monstock:           Optional[str] = None
    fournisseur_rue:         Optional[str] = None
    fournisseur_code_postal: Optional[str] = None
    fournisseur_ville:       Optional[str] = None
    fournisseur_pays:        Optional[str] = None
    fournisseur_contact:   Optional[str] = None
    fournisseur_email:     Optional[str] = None
    fournisseur_tel:       Optional[str] = None
    interlocuteurs_fournisseur: Optional[str] = None
    livraison_nom:         Optional[str] = None
    livraison_rue:         Optional[str] = None
    livraison_code_postal: Optional[str] = None
    livraison_ville:       Optional[str] = None
    livraison_pays:        Optional[str] = None
    incoterm:              Optional[str] = None
    lieu_livraison_texte:  Optional[str] = None
    delai_livraison_texte: Optional[str] = None
    conditions_paiement_texte: Optional[str] = None
    garantie_texte:        Optional[str] = None
    charge_commande_nom:   Optional[str] = None
    charge_commande_email: Optional[str] = None
    charge_commande_tel:   Optional[str] = None
    date_commande:         Optional[str] = None
    date_livraison_prevue: Optional[str] = None
    date_livraison_reelle: Optional[str] = None
    date_reglement:        Optional[str] = None
    statut:                Optional[str] = None
    conditions:            Optional[str] = None
    notes:                 Optional[str] = None
    exonere_tva:           Optional[int] = None
    frais_port:            Optional[float] = None
    lignes:                Optional[List[IntentionAchatLigneIn]] = None


class IntentionAchatOut(BaseModel):
    id:                    str
    affaire_id:            Optional[str] = None
    affaire_num:           Optional[str] = None
    affaire_nom:           Optional[str] = None
    num_ia:                str
    langue:                str = "fr"
    reference_devis:       str = ""
    reference_client:      str = ""
    fournisseur_nom:       str = ""
    reference_fournisseur:   str = ""
    reference_monstock:      str = ""
    lien_monstock:           str = ""
    fournisseur_rue:         str = ""
    fournisseur_code_postal: str = ""
    fournisseur_ville:       str = ""
    fournisseur_pays:        str = "France"
    fournisseur_contact:   str = ""
    fournisseur_email:     str = ""
    fournisseur_tel:       str = ""
    interlocuteurs_fournisseur: str = "[]"
    livraison_nom:         str = ""
    livraison_rue:         str = ""
    livraison_code_postal: str = ""
    livraison_ville:       str = ""
    livraison_pays:        str = "France"
    incoterm:              str = ""
    lieu_livraison_texte:  str = ""
    delai_livraison_texte: str = ""
    conditions_paiement_texte: str = ""
    garantie_texte:        str = ""
    charge_commande_nom:   str = ""
    charge_commande_email: str = ""
    charge_commande_tel:   str = ""
    date_commande:         str = ""
    date_livraison_prevue: str = ""
    date_livraison_reelle: str = ""
    date_reglement:        str = ""
    statut:                str = "Brouillon"
    conditions:            str = ""
    notes:                 str = ""
    exonere_tva:           int = 0
    frais_port:            float = 0.0
    date_generation:       Optional[datetime] = None
    pdf_path:              str = ""
    version:               int = 1
    lignes:                List[IntentionAchatLigneOut] = []
    total_lignes_ht:       float = 0
    total_ht:              float = 0
    total_ttc:             float = 0
    created_at:            Optional[datetime] = None
    updated_at:            Optional[datetime] = None

    model_config = {"from_attributes": True}
