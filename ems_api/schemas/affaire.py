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


class AffaireCoutLigneCreate(BaseModel):
    categorie:    str = ""
    libelle:      str = ""
    cout_prevu:   float = 0.0
    cout_reel:    float = 0.0
    stade:        str = "P1"
    poste_lie_id: Optional[str] = None
    commentaire:  str = ""
    ordre:        int = 0


class AffaireCoutLigneUpdate(BaseModel):
    categorie:    Optional[str] = None
    libelle:      Optional[str] = None
    cout_prevu:   Optional[float] = None
    cout_reel:    Optional[float] = None
    stade:        Optional[str] = None
    poste_lie_id: Optional[str] = None
    commentaire:  Optional[str] = None
    ordre:        Optional[int] = None


class AffaireCoutLigneOut(BaseModel):
    id:               str
    affaire_id:       str
    categorie:        str
    libelle:          str
    cout_prevu:       float
    cout_reel:        float
    stade:            str = "P1"
    bon_commande_id:  Optional[str] = None
    poste_lie_id:     Optional[str] = None
    commentaire:      str
    ordre:            int
    created_at:       Optional[datetime] = None
    updated_at:       Optional[datetime] = None

    model_config = {"from_attributes": True}


class AffaireCreate(BaseModel):
    num_affaire:             str = ""
    complexite:              str = ""
    client_id:               Optional[str] = None
    nom_projet:              str = ""
    navire_machine:          str = ""
    navire_immatriculation:  str = ""
    navire_port_attache:     str = ""
    ref_interne:             str = ""
    num_commande_client:     str = ""
    charge_affaire:          str = ""
    resp_technique:          str = ""
    commercial:              str = ""
    commercial_email:        str = ""
    commercial_tel:          str = ""
    date_debut:              str = ""
    date_fat:                str = ""
    date_fin_fat:            str = ""
    date_fin_prevue:         str = ""
    date_cloture:            str = ""
    date_visite_appli_debut: str = ""
    date_visite_appli_fin:   str = ""
    date_commissioning_debut: str = ""
    date_commissioning_fin:  str = ""
    statut:                  str = "En cours"
    description:             str = ""
    commentaires:            str = ""
    dossier_path:            str = ""
    prix_ht:                 str = ""
    exonere_tva:             int = 0
    date_achat:              str = ""
    fournisseur:             str = ""
    reference_fournisseur:   str = ""
    etablissement_financier: str = ""
    echeances_facturation:   str = "[]"
    lots_vendus:              str = "[]"
    whiteboard:              str = ""
    transporteur:            str = ""
    contact_transport:       str = ""
    prix_transport:          str = ""
    num_suivi_transport:     str = ""
    instructions_transport:  str = ""
    livraison_nom:           str = ""
    livraison_rue:           str = ""
    livraison_code_postal:   str = ""
    livraison_ville:         str = ""
    livraison_pays:          str = "France"
    conditions_reglement:    str = ""
    garanties:               str = ""
    interlocuteurs_client:   str = "[]"


class AffaireUpdate(BaseModel):
    complexite:              Optional[str] = None
    client_id:               Optional[str] = None
    nom_projet:              Optional[str] = None
    navire_machine:          Optional[str] = None
    navire_immatriculation:  Optional[str] = None
    navire_port_attache:     Optional[str] = None
    ref_interne:             Optional[str] = None
    num_commande_client:     Optional[str] = None
    charge_affaire:          Optional[str] = None
    resp_technique:          Optional[str] = None
    commercial:              Optional[str] = None
    commercial_email:        Optional[str] = None
    commercial_tel:          Optional[str] = None
    date_debut:              Optional[str] = None
    date_fat:                Optional[str] = None
    date_fin_fat:            Optional[str] = None
    date_fin_prevue:         Optional[str] = None
    date_cloture:            Optional[str] = None
    date_visite_appli_debut: Optional[str] = None
    date_visite_appli_fin:   Optional[str] = None
    date_commissioning_debut: Optional[str] = None
    date_commissioning_fin:  Optional[str] = None
    statut:                  Optional[str] = None
    description:             Optional[str] = None
    commentaires:            Optional[str] = None
    dossier_path:            Optional[str] = None
    prix_ht:                 Optional[str] = None
    exonere_tva:             Optional[int] = None
    date_achat:              Optional[str] = None
    fournisseur:             Optional[str] = None
    reference_fournisseur:   Optional[str] = None
    etablissement_financier: Optional[str] = None
    echeances_facturation:   Optional[str] = None
    lots_vendus:              Optional[str] = None
    whiteboard:              Optional[str] = None
    transporteur:            Optional[str] = None
    contact_transport:       Optional[str] = None
    prix_transport:          Optional[str] = None
    num_suivi_transport:     Optional[str] = None
    instructions_transport:  Optional[str] = None
    livraison_nom:           Optional[str] = None
    livraison_rue:           Optional[str] = None
    livraison_code_postal:   Optional[str] = None
    livraison_ville:         Optional[str] = None
    livraison_pays:          Optional[str] = None
    conditions_reglement:    Optional[str] = None
    garanties:               Optional[str] = None
    interlocuteurs_client:   Optional[str] = None


class AffaireOut(BaseModel):
    id:                      str
    num_affaire:             str
    complexite:              str = ""
    client_id:               Optional[str] = None
    nom_projet:              str
    navire_machine:          str
    navire_immatriculation:  str = ""
    navire_port_attache:     str = ""
    ref_interne:             str
    num_commande_client:     str = ""
    charge_affaire:          str
    resp_technique:          str = ""
    commercial:              str = ""
    commercial_email:        str = ""
    commercial_tel:          str = ""
    date_debut:              str
    date_fat:                str = ""
    date_fin_fat:            str = ""
    date_fin_prevue:         str
    date_cloture:            str
    date_visite_appli_debut: str = ""
    date_visite_appli_fin:   str = ""
    date_commissioning_debut: str = ""
    date_commissioning_fin:  str = ""
    statut:                  str
    description:             str
    commentaires:            str
    dossier_path:            str
    prix_ht:                 str = ""
    exonere_tva:             int = 0
    date_achat:              str = ""
    fournisseur:             str = ""
    reference_fournisseur:   str = ""
    etablissement_financier: str = ""
    echeances_facturation:   str = "[]"
    lots_vendus:              str = "[]"
    whiteboard:              str = ""
    transporteur:            str = ""
    contact_transport:       str = ""
    prix_transport:          str = ""
    num_suivi_transport:     str = ""
    instructions_transport:  str = ""
    livraison_nom:           str = ""
    livraison_rue:           str = ""
    livraison_code_postal:   str = ""
    livraison_ville:         str = ""
    livraison_pays:          str = "France"
    conditions_reglement:    str = ""
    garanties:               str = ""
    interlocuteurs_client:   str = "[]"
    client_nom:              Optional[str] = ""
    nb_items:                int = 0
    total_achats:            float = 0
    created_at:              Optional[datetime] = None
    updated_at:              Optional[datetime] = None

    model_config = {"from_attributes": True}
