"""Endpoints REST pour la ressource Moteur."""
from typing import List, Optional
from uuid import uuid4
from sqlalchemy.orm import joinedload
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel

from ..database import get_db
from ..models import Moteur, Client, Affaire, AffaireItem
from ..schemas.moteur import MoteurCreate, MoteurUpdate, MoteurOut
from ..services.numerotation import code_from_num_affaire
from .navires import _upsert_navire


# ── Schémas allégés pour les sous-ensembles ──────────────────────────────────
# Un sous-ensemble EST un Moteur (parent_moteur_id renseigné). On expose
# un sous-ensemble de champs plus simples que le modèle complet.
class SousEnsembleCreate(BaseModel):
    libelle:   str
    type:      str = ""
    reference: str = ""
    marque:    str = ""
    num_serie: str = ""
    etat:      str = ""
    notes:     str = ""

class SousEnsembleUpdate(BaseModel):
    libelle:   Optional[str] = None
    type:      Optional[str] = None
    reference: Optional[str] = None
    marque:    Optional[str] = None
    num_serie: Optional[str] = None
    etat:      Optional[str] = None
    notes:     Optional[str] = None

def _se_to_out(m: Moteur) -> dict:
    return {
        "id":        m.id,
        "libelle":   m.type_moteur      or "",
        "type":      m.famille          or "",
        "reference": m.ref_constructeur or "",
        "marque":    m.marque           or "",
        "num_serie": m.num_serie        or "",
        "etat":      m.application      or "",
        "notes":     m.collection       or "",
    }

router = APIRouter(prefix="/moteurs", tags=["moteurs"])


def _to_out(m: Moteur, affaire_liee: bool = False) -> dict:
    """Sérialise un moteur en garantissant TOUS les champs (jamais None)."""
    d = {}
    for c in m.__table__.columns:
        val = getattr(m, c.name)
        # Convertir None en "" pour les colonnes string
        if val is None and not c.name.endswith("_at"):
            val = ""
        d[c.name] = val
    d["client_nom"] = m.client.nom if m.client else ""
    d["nb_sous_ensembles"] = len(m.sous_ensembles)
    d["affaire_liee"] = affaire_liee
    return d


def _resolve_affaires_liees(db: Session, moteurs: List[Moteur]) -> dict:
    """Rattache chaque moteur à son affaire, corrige code_affaire si besoin.

    Deux sources, dans l'ordre de confiance :
    1. lien "réel" : le moteur est référencé (par n° de série) comme chapitre
       d'une affaire — c'est ce lien qui fait foi.
    2. lien déclaratif : le champ code_affaire du moteur correspond au code
       court AAAANNNN (cf. code_from_num_affaire) d'une affaire existante,
       ou à son ref_interne.
    Si un lien réel est trouvé et que code_affaire est vide ou périmé, il est
    corrigé automatiquement (toujours stocké sous forme AAAANNNN, pas le
    num_affaire complet). Retourne {moteur_id: bool(lié)}.
    """
    if not moteurs:
        return {}

    series = [m.num_serie for m in moteurs if m.num_serie]
    by_serie = {}
    if series:
        rows = (db.query(AffaireItem.num_serie, Affaire)
                  .join(Affaire, Affaire.id == AffaireItem.affaire_id)
                  .filter(AffaireItem.num_serie.in_(series))
                  .order_by(AffaireItem.updated_at.desc())
                  .all())
        for ns, aff in rows:
            by_serie.setdefault(ns, aff)

    codes = {m.code_affaire for m in moteurs if m.code_affaire}
    by_code = {}
    if codes:
        # Pas d'index sur le code court : on compare en Python après avoir
        # chargé les affaires candidates (par ref_interne exact, ou toutes
        # pour dériver leur code AAAANNNN).
        for aff in db.query(Affaire).all():
            c = code_from_num_affaire(aff.num_affaire)
            if c in codes:
                by_code[c] = aff
            if aff.ref_interne in codes:
                by_code[aff.ref_interne] = aff

    result = {}
    dirty = False
    for m in moteurs:
        aff = by_serie.get(m.num_serie) or \
            (by_code.get(m.code_affaire) if m.code_affaire else None)
        if aff:
            code = code_from_num_affaire(aff.num_affaire)
            if m.code_affaire != code:
                m.code_affaire = code
                dirty = True
        result[m.id] = bool(aff)
    if dirty:
        db.commit()
    return result


def sync_moteur_apres_suppression_lien(db: Session, num_serie: str, affaire_id: str) -> None:
    """Efface code_affaire d'un moteur quand le chapitre qui le rattachait à
    cette affaire (par n° de série) vient d'être supprimé ou modifié.

    Sans cela, code_affaire reste figé sur une affaire dont le moteur n'est
    plus réellement un chapitre : la liste des moteurs continue d'afficher
    l'alerte "déjà lié à l'affaire X" alors que ce n'est plus le cas.
    N'efface que si aucun autre chapitre de la même affaire ne référence
    encore ce n° de série (ex. deux chapitres pointant le même moteur).
    """
    if not num_serie:
        return
    m = db.query(Moteur).filter(Moteur.num_serie == num_serie).first()
    if not m or not m.code_affaire:
        return
    aff = db.query(Affaire).filter(Affaire.id == affaire_id).first()
    if not aff or m.code_affaire != code_from_num_affaire(aff.num_affaire):
        return
    still_linked = db.query(AffaireItem).filter(
        AffaireItem.affaire_id == affaire_id,
        AffaireItem.num_serie == num_serie,
    ).first()
    if not still_linked:
        m.code_affaire = ""
        db.commit()


def clear_moteurs_code_affaire(db: Session, affaire: Affaire) -> None:
    """Efface code_affaire de tous les moteurs pointant vers cette affaire.

    À appeler avant la suppression d'une affaire : ses AffaireItem
    disparaissent avec elle (cascade), donc rien d'autre ne nettoierait ce
    champ déclaratif ensuite.
    """
    code = code_from_num_affaire(affaire.num_affaire)
    if not code:
        return
    db.query(Moteur).filter(Moteur.code_affaire == code).update({"code_affaire": ""})
    db.commit()


@router.get("", response_model=List[MoteurOut])
def list_moteurs(
    search: Optional[str] = Query(None),
    serie_only: bool = Query(False, description="Recherche uniquement par N° série"),
    parent_id: Optional[str] = Query(
        None, description="Si renseigné, retourne uniquement les sous-ensembles de ce moteur"),
    db: Session = Depends(get_db),
):
    q = db.query(Moteur).options(
        joinedload(Moteur.client),
        joinedload(Moteur.sous_ensembles),
    )
    if parent_id:
        moteurs = (q.filter(Moteur.parent_moteur_id == parent_id)
                    .order_by(Moteur.num_serie).all())
        liens = _resolve_affaires_liees(db, moteurs)
        return [_to_out(m, liens[m.id]) for m in moteurs]
    # Recherche principale : uniquement les moteurs racine, les
    # sous-ensembles se déroulent via la flèche dans la liste.
    q = q.filter(Moteur.parent_moteur_id.is_(None))
    if search:
        like = f"%{search}%"
        if serie_only:
            q = q.filter(Moteur.num_serie.ilike(like))
        else:
            # outerjoin Client pour pouvoir chercher par nom client
            q = q.outerjoin(Client).filter(
                or_(Moteur.num_serie.ilike(like),
                    Moteur.marque.ilike(like),
                    Moteur.navire.ilike(like),
                    Moteur.machine.ilike(like),
                    Moteur.ref_constructeur.ilike(like),
                    Moteur.code_affaire.ilike(like),
                    Client.nom.ilike(like)))
    moteurs = q.order_by(Moteur.num_serie).all()
    liens = _resolve_affaires_liees(db, moteurs)
    return [_to_out(m, liens[m.id]) for m in moteurs]


@router.get("/garantie-expirante", response_model=List[MoteurOut])
def list_moteurs_garantie_expirante(
    jours_max: int = Query(90, description="Jours avant expiration"),
    db: Session = Depends(get_db),
):
    """Moteurs dont la garantie (date + durée) expire dans les N jours."""
    from datetime import datetime, timedelta
    moteurs = db.query(Moteur).all()
    res = []
    seuil = datetime.now() + timedelta(days=jours_max)
    for m in moteurs:
        if not m.date_mise_service or not m.duree_garantie:
            continue
        try:
            d = datetime.strptime(m.date_mise_service, "%d/%m/%Y")
            mois = int(str(m.duree_garantie).strip())
            fin = d + timedelta(days=mois * 30)
            if datetime.now() <= fin <= seuil:
                res.append(_to_out(m))
        except (ValueError, TypeError):
            continue
    return res


@router.get("/by-serie/{num_serie}", response_model=Optional[MoteurOut])
def find_by_serie(num_serie: str, db: Session = Depends(get_db)):
    m = db.query(Moteur).filter(Moteur.num_serie == num_serie).first()
    if not m:
        return None
    liens = _resolve_affaires_liees(db, [m])
    return _to_out(m, liens[m.id])


@router.get("/{moteur_id}", response_model=MoteurOut)
def get_moteur(moteur_id: str, db: Session = Depends(get_db)):
    m = db.query(Moteur).filter(Moteur.id == moteur_id).first()
    if not m:
        raise HTTPException(404, f"Moteur {moteur_id} introuvable")
    liens = _resolve_affaires_liees(db, [m])
    return _to_out(m, liens[m.id])


@router.post("", response_model=MoteurOut, status_code=status.HTTP_201_CREATED)
def create_moteur(data: MoteurCreate, db: Session = Depends(get_db)):
    """Crée ou met à jour un moteur (upsert sur num_serie)."""
    if not db.query(Client).filter(Client.id == data.client_id).first():
        raise HTTPException(400, f"Client {data.client_id} introuvable")
    existing = db.query(Moteur).filter(Moteur.num_serie == data.num_serie).first()
    if existing:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(existing, field, value)
        _upsert_navire(db, existing.navire, existing.navire_immatriculation,
                      existing.navire_port_attache, existing.client_id)
        db.commit()
        db.refresh(existing)
        return _to_out(existing)
    m = Moteur(id=str(uuid4()), **data.model_dump())
    db.add(m)
    _upsert_navire(db, m.navire, m.navire_immatriculation,
                  m.navire_port_attache, m.client_id)
    db.commit()
    db.refresh(m)
    return _to_out(m)


@router.put("/{moteur_id}", response_model=MoteurOut)
def update_moteur(moteur_id: str, data: MoteurUpdate,
                  db: Session = Depends(get_db)):
    m = db.query(Moteur).filter(Moteur.id == moteur_id).first()
    if not m:
        raise HTTPException(404, f"Moteur {moteur_id} introuvable")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(m, field, value)
    if data.navire is not None or data.navire_immatriculation is not None \
            or data.navire_port_attache is not None:
        _upsert_navire(db, m.navire, m.navire_immatriculation,
                      m.navire_port_attache, m.client_id)
    m.version = (m.version or 0) + 1
    db.commit()
    db.refresh(m)
    return _to_out(m)


@router.delete("/{moteur_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_moteur(moteur_id: str, db: Session = Depends(get_db)):
    m = db.query(Moteur).filter(Moteur.id == moteur_id).first()
    if not m:
        raise HTTPException(404, f"Moteur {moteur_id} introuvable")
    db.delete(m)
    db.commit()
    return None


# ─── Sous-ensembles d'un moteur ──────────────────────────────────────────────

@router.get("/{moteur_id}/sous-ensembles")
def list_sous_ensembles(moteur_id: str, db: Session = Depends(get_db)):
    if not db.query(Moteur).filter(Moteur.id == moteur_id).first():
        raise HTTPException(404, "Moteur introuvable")
    items = (db.query(Moteur)
               .filter(Moteur.parent_moteur_id == moteur_id)
               .order_by(Moteur.type_moteur)
               .all())
    return [_se_to_out(m) for m in items]


@router.post("/{moteur_id}/sous-ensembles", status_code=201)
def add_sous_ensemble(moteur_id: str, body: SousEnsembleCreate,
                      db: Session = Depends(get_db)):
    parent = db.query(Moteur).filter(Moteur.id == moteur_id).first()
    if not parent:
        raise HTTPException(404, "Moteur introuvable")
    ns = body.num_serie.strip() if body.num_serie.strip() else f"SE-{str(uuid4())[:8]}"
    while db.query(Moteur).filter(Moteur.num_serie == ns).first():
        ns = f"SE-{str(uuid4())[:8]}"
    m = Moteur(
        id=str(uuid4()),
        parent_moteur_id=moteur_id,
        client_id=parent.client_id,
        num_serie=ns,
        type_moteur=body.libelle,
        famille=body.type,
        ref_constructeur=body.reference,
        marque=body.marque,
        application=body.etat,
        collection=body.notes,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return _se_to_out(m)


@router.put("/{moteur_id}/sous-ensembles/{se_id}")
def update_sous_ensemble(moteur_id: str, se_id: str, body: SousEnsembleUpdate,
                         db: Session = Depends(get_db)):
    m = db.query(Moteur).filter(
        Moteur.id == se_id, Moteur.parent_moteur_id == moteur_id
    ).first()
    if not m:
        raise HTTPException(404, "Sous-ensemble introuvable")
    if body.libelle   is not None: m.type_moteur      = body.libelle
    if body.type      is not None: m.famille           = body.type
    if body.reference is not None: m.ref_constructeur = body.reference
    if body.marque    is not None: m.marque            = body.marque
    if body.etat      is not None: m.application       = body.etat
    if body.notes     is not None: m.collection        = body.notes
    if body.num_serie is not None and body.num_serie.strip():
        ns = body.num_serie.strip()
        if db.query(Moteur).filter(Moteur.num_serie == ns, Moteur.id != se_id).first():
            raise HTTPException(400, f"N° série {ns} déjà utilisé")
        m.num_serie = ns
    db.commit()
    db.refresh(m)
    return _se_to_out(m)


@router.delete("/{moteur_id}/sous-ensembles/{se_id}", status_code=204)
def delete_sous_ensemble(moteur_id: str, se_id: str, db: Session = Depends(get_db)):
    m = db.query(Moteur).filter(
        Moteur.id == se_id, Moteur.parent_moteur_id == moteur_id
    ).first()
    if not m:
        raise HTTPException(404, "Sous-ensemble introuvable")
    db.delete(m)
    db.commit()
