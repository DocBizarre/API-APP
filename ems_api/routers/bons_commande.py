"""Endpoints REST pour les bons de commande (achats), liés ou non à une affaire."""
from datetime import datetime
from typing import List, Optional
from uuid import uuid4
import json as _json_mod

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..schemas.bon_commande import EnvoiIn
from ..database import get_db
from ..models.affaire import Affaire, AffaireCoutLigne
from ..models.piece import Piece
from ..models.bon_commande import BonCommande, BonCommandeLigne
from ..models.reception_achat import ReceptionAchat, ReceptionAchatLigne
from ..schemas.bon_commande import (
    BonCommandeCreate, BonCommandeUpdate, BonCommandeOut,
    ReceptionCreate, ReceptionOut,
)
from ..services.numerotation import next_num_bon_commande
from .affaires import _get_dossier, _create_arborescence
from .interventions import _upsert_contact
from .fournisseurs import _upsert_fournisseur
from ..services.piece_fournisseurs import lier_lignes_achat

router = APIRouter(prefix="/bons-commande", tags=["bons-commande"])

STATUTS = ["Brouillon", "Envoyé", "Confirmé", "Reçu partiellement", "Reçu", "Annulé"]

# Tolérance de comparaison des quantités (saisies décimales)
_EPS = 1e-6


def _coerce(c, val):
    if val is not None:
        return val
    type_str = str(c.type)
    if type_str.startswith(("FLOAT", "INTEGER")):
        return 0
    if type_str.startswith(("DATETIME", "DATE")):
        return None
    return ""


def _recu_par_ligne(bc: BonCommande) -> dict:
    """Quantité déjà reçue pour chaque ligne du bon (id de ligne -> quantité)."""
    recu: dict = {}
    for r in bc.receptions:
        for rl in r.lignes:
            if rl.bon_commande_ligne_id:
                recu[rl.bon_commande_ligne_id] = (recu.get(rl.bon_commande_ligne_id, 0)
                                                  + (rl.quantite_recue or 0))
    return recu


def _etat_reception(bc: BonCommande, recu: Optional[dict] = None) -> str:
    """Renvoie "" (rien reçu), "partielle" ou "complete". Les lignes à quantité
    nulle (commentaires, lignes de service) ne comptent pas."""
    recu = _recu_par_ligne(bc) if recu is None else recu
    lignes = [l for l in bc.lignes if (l.quantite or 0) > _EPS]
    if not lignes or not any(recu.get(l.id, 0) > _EPS for l in lignes):
        return ""
    if all(recu.get(l.id, 0) >= (l.quantite or 0) - _EPS for l in lignes):
        return "complete"
    return "partielle"


def _date_fr_key(s: str):
    try:
        j, m, a = (int(x) for x in (s or "").split("/"))
        return (a, m, j)
    except Exception:
        return (0, 0, 0)


def _appliquer_etat_reception(bc: BonCommande) -> None:
    """Aligne le statut (et la date de livraison réelle) du bon sur ses réceptions."""
    if bc.statut == "Annulé":
        return
    ancien = bc.statut
    etat = _etat_reception(bc)
    if etat == "complete":
        bc.statut = "Reçu"
        dates = [r.date_reception for r in bc.receptions if r.date_reception]
        if dates:
            bc.date_livraison_reelle = max(dates, key=_date_fr_key)
        return
    if ancien == "Reçu":
        # N'est plus entièrement reçu (réception annulée, ligne ajoutée…)
        bc.date_livraison_reelle = ""
    if etat == "partielle":
        bc.statut = "Reçu partiellement"
    elif ancien in ("Reçu", "Reçu partiellement"):
        bc.statut = "Confirmé"


def _ligne_to_out(l: BonCommandeLigne, recu: Optional[dict] = None) -> dict:
    d = {}
    for c in l.__table__.columns:
        d[c.name] = _coerce(c, getattr(l, c.name))
    d["piece_id"] = l.piece_id  # préserver None (pas de piece cataloguée)
    q_recue = (recu or {}).get(l.id, 0)
    d["quantite_recue"] = q_recue
    d["quantite_restante"] = max((l.quantite or 0) - q_recue, 0)
    return d


def _reception_to_out(r: ReceptionAchat) -> dict:
    return {
        "id": r.id,
        "bon_commande_id": r.bon_commande_id,
        "date_reception": r.date_reception or "",
        "numero_bl": r.numero_bl or "",
        "receptionnaire": r.receptionnaire or "",
        "commentaire": r.commentaire or "",
        "created_at": r.created_at,
        "lignes": [{
            "id": rl.id,
            "bon_commande_ligne_id": rl.bon_commande_ligne_id,
            "reference": rl.reference or "",
            "libelle": rl.libelle or "",
            "quantite_recue": rl.quantite_recue or 0,
        } for rl in r.lignes],
    }


def _to_out(bc: BonCommande) -> dict:
    d = {}
    for c in bc.__table__.columns:
        d[c.name] = _coerce(c, getattr(bc, c.name))
    d["affaire_id"] = bc.affaire_id  # préserver None (non-lié), pas de coercition en ""
    recu = _recu_par_ligne(bc)
    d["lignes"] = [_ligne_to_out(l, recu) for l in bc.lignes]
    d["receptions"] = [_reception_to_out(r) for r in bc.receptions]
    d["etat_reception"] = _etat_reception(bc, recu)
    total_lignes_ht = sum(l.montant_ligne or 0 for l in bc.lignes)
    total_ht = total_lignes_ht + (bc.frais_port or 0)
    d["total_lignes_ht"] = total_lignes_ht
    d["total_ht"] = total_ht
    d["total_ttc"] = total_ht if bc.exonere_tva else round(total_ht * 1.20, 2)
    d["affaire_num"] = bc.affaire.num_affaire if bc.affaire else None
    d["affaire_nom"] = bc.affaire.nom_projet if bc.affaire else None
    return d


def _get_bon(bc_id: str, db: Session) -> BonCommande:
    bc = db.query(BonCommande).filter(BonCommande.id == bc_id).first()
    if not bc:
        raise HTTPException(404, "Bon de commande introuvable")
    return bc


def _upsert_interlocuteurs_fournisseur(db: Session, interlocuteurs_json: str) -> None:
    """Mémorise chaque interlocuteur fournisseur dans la table contacts (autocomplétion)."""
    try:
        interlocuteurs = _json_mod.loads(interlocuteurs_json or "[]")
    except Exception:
        interlocuteurs = []
    for it in interlocuteurs:
        _upsert_contact(db, it.get("nom", ""), it.get("email", ""), it.get("telephone", ""))


def _check_affaire(affaire_id: Optional[str], db: Session) -> None:
    if affaire_id and not db.query(Affaire).filter(Affaire.id == affaire_id).first():
        raise HTTPException(404, f"Affaire {affaire_id} introuvable")


def _recalc_lignes(bc: BonCommande, lignes_in: list, db: Session) -> None:
    """Remplace les lignes du bon de commande par `lignes_in`.

    Les lignes existantes sont mises à jour en place (même id) plutôt que
    recréées, car les réceptions y sont rattachées par leur id : une ligne
    entrante est associée à une ligne existante par son `id`, ou à défaut
    (client qui n'envoie pas l'id) par (référence, désignation). Les lignes
    existantes non associées sont supprimées."""
    existantes = {l.id: l for l in bc.lignes}
    ids_explicites = {getattr(li, "id", None) for li in lignes_in} & existantes.keys()
    prises: set = set()

    def _associer(ligne):
        lid = getattr(ligne, "id", None)
        if lid in existantes and lid not in prises:
            return existantes[lid]
        for l in bc.lignes:
            if (l.id not in prises and l.id not in ids_explicites
                    and (l.reference or "") == (ligne.reference or "")
                    and (l.libelle or "") == (ligne.libelle or "")):
                return l
        return None

    for i, ligne in enumerate(lignes_in):
        piece_id = ligne.piece_id or None
        if piece_id and not db.query(Piece).filter(Piece.id == piece_id).first():
            piece_id = None
        montant = round((ligne.quantite or 0) * (ligne.prix_unitaire or 0), 2)
        valeurs = dict(
            piece_id=piece_id,
            reference=ligne.reference,
            libelle=ligne.libelle,
            quantite=ligne.quantite,
            prix_unitaire=ligne.prix_unitaire,
            montant_ligne=montant,
            ordre=ligne.ordre or i,
        )
        cible = _associer(ligne)
        if cible is not None:
            prises.add(cible.id)
            for k, v in valeurs.items():
                setattr(cible, k, v)
        else:
            db.add(BonCommandeLigne(id=str(uuid4()), bon_commande_id=bc.id, **valeurs))
    for lid, l in existantes.items():
        if lid not in prises:
            db.delete(l)


def _sync_cout_ligne_from_bc(bc: BonCommande, db: Session) -> None:
    """Synchronise le poste de bilan (P2) généré depuis ce bon de commande."""
    existing = db.query(AffaireCoutLigne).filter(
        AffaireCoutLigne.bon_commande_id == bc.id
    ).first()
    if bc.affaire_id:
        # Le poste de bilan est créé dès qu'un achat est lié à l'affaire, même
        # sans chapitre choisi : il apparaît alors comme "non affecté" dans le
        # bilan, à assigner à un poste plutôt que de disparaître silencieusement.
        montant = sum(l.montant_ligne or 0 for l in bc.lignes) + (bc.frais_port or 0)
        libelle = f"BC {bc.num_bc}" + (f" — {bc.fournisseur_nom}" if bc.fournisseur_nom else "")
        commentaire = f"Généré automatiquement depuis le bon de commande {bc.num_bc}."
        if existing:
            existing.affaire_id = bc.affaire_id
            existing.categorie = bc.chapitre_cout or ""
            existing.libelle = libelle
            existing.stade = "P2"
            existing.cout_prevu = 0
            existing.cout_reel = montant
            existing.commentaire = commentaire
        else:
            db.add(AffaireCoutLigne(
                id=str(uuid4()),
                affaire_id=bc.affaire_id,
                bon_commande_id=bc.id,
                categorie=bc.chapitre_cout or "",
                libelle=libelle,
                stade="P2",
                cout_prevu=0,
                cout_reel=montant,
                commentaire=commentaire,
                ordre=9999,
            ))
    elif existing:
        db.delete(existing)


@router.get("", response_model=List[BonCommandeOut])
def list_bons_commande(
    affaire_id: Optional[str] = Query(None),
    statut: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(BonCommande)
    if affaire_id:
        q = q.filter(BonCommande.affaire_id == affaire_id)
    if statut:
        q = q.filter(BonCommande.statut == statut)
    if search:
        like = f"%{search}%"
        q = q.filter(or_(BonCommande.num_bc.ilike(like),
                         BonCommande.fournisseur_nom.ilike(like)))
    q = q.order_by(BonCommande.created_at.desc())
    return [_to_out(bc) for bc in q.all()]


@router.get("/statuts")
def get_statuts():
    return STATUTS


@router.get("/{bc_id}", response_model=BonCommandeOut)
def get_bon_commande(bc_id: str, db: Session = Depends(get_db)):
    return _to_out(_get_bon(bc_id, db))


@router.post("", response_model=BonCommandeOut, status_code=201)
def create_bon_commande(body: BonCommandeCreate, db: Session = Depends(get_db)):
    _check_affaire(body.affaire_id, db)
    bc = BonCommande(
        id=str(uuid4()),
        affaire_id=body.affaire_id or None,
        num_bc=next_num_bon_commande(db),
        fournisseur_nom=body.fournisseur_nom,
        reference_fournisseur=body.reference_fournisseur,
        reference_monstock=body.reference_monstock,
        lien_monstock=body.lien_monstock,
        fournisseur_rue=body.fournisseur_rue,
        fournisseur_code_postal=body.fournisseur_code_postal,
        fournisseur_ville=body.fournisseur_ville,
        fournisseur_pays=body.fournisseur_pays,
        fournisseur_contact=body.fournisseur_contact,
        fournisseur_email=body.fournisseur_email,
        fournisseur_tel=body.fournisseur_tel,
        interlocuteurs_fournisseur=body.interlocuteurs_fournisseur,
        livraison_nom=body.livraison_nom,
        livraison_rue=body.livraison_rue,
        livraison_code_postal=body.livraison_code_postal,
        livraison_ville=body.livraison_ville,
        livraison_pays=body.livraison_pays,
        charge_commande_nom=body.charge_commande_nom,
        charge_commande_email=body.charge_commande_email,
        charge_commande_tel=body.charge_commande_tel,
        date_commande=body.date_commande,
        date_livraison_prevue=body.date_livraison_prevue,
        date_livraison_reelle=body.date_livraison_reelle,
        date_reglement=body.date_reglement,
        statut=body.statut,
        conditions=body.conditions,
        notes=body.notes,
        exonere_tva=body.exonere_tva,
        frais_port=body.frais_port,
        chapitre_cout=body.chapitre_cout,
        paiements=body.paiements,
    )
    db.add(bc)
    db.flush()
    _recalc_lignes(bc, body.lignes, db)
    _upsert_fournisseur(db, bc.fournisseur_nom, bc.fournisseur_contact, bc.fournisseur_email,
                       bc.fournisseur_tel, bc.fournisseur_rue, bc.fournisseur_code_postal,
                       bc.fournisseur_ville, bc.fournisseur_pays)
    _upsert_interlocuteurs_fournisseur(db, bc.interlocuteurs_fournisseur)
    lier_lignes_achat(db, bc.fournisseur_nom, body.lignes, bc.date_commande)
    db.commit()
    db.refresh(bc)
    _sync_cout_ligne_from_bc(bc, db)
    db.commit()
    return _to_out(bc)


@router.put("/{bc_id}", response_model=BonCommandeOut)
def update_bon_commande(bc_id: str, body: BonCommandeUpdate,
                        db: Session = Depends(get_db)):
    bc = _get_bon(bc_id, db)
    data = body.model_dump(exclude_unset=True)
    lignes = data.pop("lignes", None)
    if "affaire_id" in data:
        aid = data.pop("affaire_id")
        _check_affaire(aid, db)
        bc.affaire_id = aid or None
    for field, val in data.items():
        if val is not None:
            setattr(bc, field, val)
    if lignes is not None:
        _recalc_lignes(bc, body.lignes, db)
    _upsert_fournisseur(db, bc.fournisseur_nom, bc.fournisseur_contact, bc.fournisseur_email,
                       bc.fournisseur_tel, bc.fournisseur_rue, bc.fournisseur_code_postal,
                       bc.fournisseur_ville, bc.fournisseur_pays)
    _upsert_interlocuteurs_fournisseur(db, bc.interlocuteurs_fournisseur)
    lier_lignes_achat(db, bc.fournisseur_nom,
                      body.lignes if lignes is not None else list(bc.lignes),
                      bc.date_commande)
    bc.version = (bc.version or 1) + 1
    db.commit()
    db.refresh(bc)
    if lignes is not None and bc.receptions:
        # Lignes modifiées (quantité, ajout…) : l'état de réception peut changer
        _appliquer_etat_reception(bc)
    _sync_cout_ligne_from_bc(bc, db)
    db.commit()
    return _to_out(bc)


@router.delete("/{bc_id}", status_code=204)
def delete_bon_commande(bc_id: str, db: Session = Depends(get_db)):
    bc = _get_bon(bc_id, db)
    db.query(AffaireCoutLigne).filter(AffaireCoutLigne.bon_commande_id == bc_id).delete()
    db.delete(bc)
    db.commit()


@router.get("/{bc_id}/pdf",
            summary="Génère, archive (si lié à une affaire) et renvoie le bon de commande en PDF",
            response_class=Response)
def generer_pdf_bon_commande(bc_id: str, db: Session = Depends(get_db)):
    try:
        from weasyprint import HTML
    except ImportError as e:
        raise HTTPException(500, f"WeasyPrint non installé sur le serveur : {e}")

    try:
        from shared.affaire_pdf import build_bon_commande_html
    except ImportError as e:
        raise HTTPException(500, f"shared.affaire_pdf indisponible : {e}")

    bc = _get_bon(bc_id, db)
    a = db.query(Affaire).filter(Affaire.id == bc.affaire_id).first() if bc.affaire_id else None

    a_dict = {c.name: getattr(a, c.name) for c in a.__table__.columns} if a else None
    bc_dict = {c.name: getattr(bc, c.name) for c in bc.__table__.columns}
    lignes = [
        {c.name: getattr(l, c.name) for c in l.__table__.columns}
        for l in bc.lignes
    ]

    html_str = build_bon_commande_html(bc_dict, lignes, affaire=a_dict)

    try:
        pdf_bytes = HTML(string=html_str).write_pdf()
    except Exception as e:
        raise HTTPException(500, f"Échec génération PDF (WeasyPrint) : {e}")

    safe_num = bc.num_bc.replace("/", "-").replace(" ", "_")

    if a:
        try:
            dossier = _get_dossier(a.id, db)
            _create_arborescence(dossier)
            dest = dossier / "ACHAT" / "FOURNISSEURS" / f"BC_{safe_num}.pdf"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(pdf_bytes)
            bc.pdf_path = str(dest)
        except Exception:
            pass  # l'archivage disque est un plus, ne doit pas bloquer le téléchargement

    bc.date_generation = datetime.now()
    db.commit()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="BC_{safe_num}.pdf"',
            "Cache-Control": "no-store",
        },
    )

@router.post("/{bc_id}/envoi", response_model=BonCommandeOut,
             summary="Marque la commande comme envoyée au fournisseur (ou annule)")
def marquer_envoi(bc_id: str, body: EnvoiIn, db: Session = Depends(get_db)):
    obj = _get_bon(bc_id, db)
    if body.envoye:
        obj.envoye_le = datetime.now().strftime("%d/%m/%Y %H:%M")
        obj.envoye_a = (body.envoye_a or "").strip()
        if (obj.statut or "Brouillon") == "Brouillon":
            obj.statut = "Envoyé"
    else:
        obj.envoye_le = ""
        obj.envoye_a = ""
    obj.version = (obj.version or 1) + 1
    db.commit()
    db.refresh(obj)
    return _to_out(obj)


# ── Réceptions (livraisons fournisseur, éventuellement partielles) ──

@router.get("/{bc_id}/receptions", response_model=List[ReceptionOut],
            summary="Historique des réceptions du bon de commande")
def list_receptions(bc_id: str, db: Session = Depends(get_db)):
    return [_reception_to_out(r) for r in _get_bon(bc_id, db).receptions]


@router.post("/{bc_id}/receptions", response_model=BonCommandeOut, status_code=201,
             summary="Enregistre une réception (totale ou partielle) des articles commandés")
def create_reception(bc_id: str, body: ReceptionCreate, db: Session = Depends(get_db)):
    bc = _get_bon(bc_id, db)
    if bc.statut == "Annulé":
        raise HTTPException(409, "Bon de commande annulé : réception impossible")
    lignes_bc = {l.id: l for l in bc.lignes}
    recu = _recu_par_ligne(bc)

    a_recevoir: dict = {}
    for rl in body.lignes:
        q = rl.quantite_recue or 0
        if q < -_EPS:
            raise HTTPException(422, "Quantité reçue négative")
        if q <= _EPS:
            continue
        if rl.ligne_id not in lignes_bc:
            raise HTTPException(422, "Ligne absente de ce bon de commande "
                                     "(le bon a été modifié entre-temps ? rechargez-le)")
        a_recevoir[rl.ligne_id] = a_recevoir.get(rl.ligne_id, 0) + q
    if not a_recevoir:
        raise HTTPException(422, "Aucune quantité reçue saisie")
    for lid, q in a_recevoir.items():
        ligne = lignes_bc[lid]
        restant = (ligne.quantite or 0) - recu.get(lid, 0)
        if q > restant + _EPS:
            nom = ligne.reference or ligne.libelle or f"ligne {(ligne.ordre or 0) + 1}"
            raise HTTPException(
                422, f"{nom} : {q:g} reçu(s) pour {max(restant, 0):g} restant(s) à recevoir")

    reception = ReceptionAchat(
        id=str(uuid4()),
        bon_commande_id=bc.id,
        date_reception=(body.date_reception or "").strip() or datetime.now().strftime("%d/%m/%Y"),
        numero_bl=(body.numero_bl or "").strip(),
        receptionnaire=(body.receptionnaire or "").strip(),
        commentaire=(body.commentaire or "").strip(),
    )
    for lid, q in a_recevoir.items():
        ligne = lignes_bc[lid]
        reception.lignes.append(ReceptionAchatLigne(
            id=str(uuid4()),
            bon_commande_ligne_id=lid,
            reference=ligne.reference or "",
            libelle=ligne.libelle or "",
            quantite_recue=q,
        ))
    bc.receptions.append(reception)
    db.flush()
    _appliquer_etat_reception(bc)
    bc.version = (bc.version or 1) + 1
    db.commit()
    db.refresh(bc)
    return _to_out(bc)


@router.delete("/{bc_id}/receptions/{reception_id}", response_model=BonCommandeOut,
               summary="Annule une réception saisie par erreur")
def delete_reception(bc_id: str, reception_id: str, db: Session = Depends(get_db)):
    bc = _get_bon(bc_id, db)
    reception = next((r for r in bc.receptions if r.id == reception_id), None)
    if reception is None:
        raise HTTPException(404, "Réception introuvable")
    bc.receptions.remove(reception)
    db.flush()
    _appliquer_etat_reception(bc)
    bc.version = (bc.version or 1) + 1
    db.commit()
    db.refresh(bc)
    return _to_out(bc)

