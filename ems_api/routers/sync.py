"""
Endpoints de synchronisation pour les tablettes terrain.

Principe (last-write-wins avec detection de conflit par numero de version) :
  • Chaque bon a un champ `version` (entier) incremente a chaque modification
    cote serveur.
  • PULL  : la tablette telecharge les bons avec leur `version` actuelle, qu'elle
            memorise comme "version de base".
  • PUSH  : la tablette renvoie ses bons modifies en joignant la `base_version`
            (la version qu'avait le serveur au moment du pull). Le serveur compare :
              - version serveur actuelle == base_version  -> pas de conflit,
                on ecrase et on incremente la version.
              - version serveur actuelle  > base_version  -> CONFLIT (modifie au
                bureau entre-temps). On ne touche a rien, on signale le conflit.
            La tablette peut repousser avec force=True pour ecraser.

  Le numero de version est incremente automatiquement a chaque modif via un
  event SQLAlchemy (voir models/intervention.py) OU manuellement dans les
  routers. Ici, le push incremente explicitement.
"""
from datetime import datetime
from typing import List, Optional, Any, Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (Intervention, Client, Moteur, Garantie,
                       Amelioration, Technicien)


router = APIRouter(prefix="/sync", tags=["sync"])


# ─── Schemas de synchro ──────────────────────────────────────────────────────
class PushBon(BaseModel):
    """Un bon renvoye par la tablette."""
    data: Dict[str, Any]               # tous les champs de l'intervention
    base_version: int = 0              # version du serveur au moment du pull
    force: bool = False                # True = ecraser meme en cas de conflit


class PushRequest(BaseModel):
    device: str = ""
    bons: List[PushBon] = []


class ConflitInfo(BaseModel):
    id: str
    num_bon: str
    serveur_version: int
    base_version: int
    serveur_updated_at: str = ""


class PushResult(BaseModel):
    appliques: int = 0
    conflits: List[ConflitInfo] = []
    erreurs: List[str] = []


def _iso(dt) -> str:
    if dt is None:
        return ""
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


def _inv_to_dict(inv: Intervention) -> dict:
    d = {}
    for c in inv.__table__.columns:
        v = getattr(inv, c.name)
        if isinstance(v, datetime):
            v = v.isoformat()
        elif v is None and not c.name.endswith("_at"):
            v = ""
        d[c.name] = v
    return d


# ═══════════════════════════════════════════════════════════════════════════
#   PULL — la tablette telecharge l'etat du serveur
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/pull/referentiels")
def pull_referentiels(db: Session = Depends(get_db)) -> dict:
    """
    Renvoie tous les referentiels (lecture seule cote tablette) :
    clients, moteurs, techniciens. Les pieces sont volumineuses (55k) donc
    fournies via l'endpoint dedie /pieces si besoin (pull separe).
    """
    def dump(rows):
        out = []
        for r in rows:
            d = {}
            for c in r.__table__.columns:
                v = getattr(r, c.name)
                if isinstance(v, datetime):
                    v = v.isoformat()
                elif v is None and not c.name.endswith("_at"):
                    v = ""
                d[c.name] = v
            out.append(d)
        return out

    return {
        "clients":     dump(db.query(Client).all()),
        "moteurs":     dump(db.query(Moteur).all()),
        "techniciens": dump(db.query(Technicien).all()),
        "garanties":   dump(db.query(Garantie).all()),
        "served_at":   datetime.now().isoformat(),
    }


@router.get("/pull/bons")
def pull_bons(db: Session = Depends(get_db)) -> dict:
    """
    Renvoie tous les bons (interventions) avec leur updated_at.
    La tablette stocke pour chacun le updated_at comme "base" de comparaison.
    """
    bons = []
    for inv in db.query(Intervention).all():
        d = _inv_to_dict(inv)
        bons.append(d)
    return {"bons": bons, "served_at": datetime.now().isoformat()}


# ═══════════════════════════════════════════════════════════════════════════
#   PUSH — la tablette renvoie ses bons modifies
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/push/bons", response_model=PushResult)
def push_bons(req: PushRequest, db: Session = Depends(get_db)) -> PushResult:
    res = PushResult()

    cols_exclues = {"created_at", "updated_at", "version"}
    cols_valides = {c.name for c in Intervention.__table__.columns}

    for pb in req.bons:
        data = pb.data or {}
        inv_id = data.get("id")
        num_bon = data.get("num_bon", "")
        if not inv_id:
            res.erreurs.append(f"Bon sans id ignore ({num_bon})")
            continue

        existing = db.query(Intervention).filter(
            Intervention.id == inv_id).first()

        # ── Cas 1 : le bon n'existe pas sur le serveur -> creation ──────────
        if not existing:
            new_kwargs = {k: v for k, v in data.items()
                          if k in cols_valides and k not in cols_exclues}
            inv = Intervention(**new_kwargs)
            if req.device:
                inv.sync_device = req.device
            inv.sync_state = "atelier"
            inv.version = 1
            db.add(inv)
            res.appliques += 1
            continue

        # ── Cas 2 : detection de conflit par numero de version ──────────────
        serveur_version = existing.version or 0
        conflit = (serveur_version > pb.base_version)

        if conflit and not pb.force:
            res.conflits.append(ConflitInfo(
                id=inv_id, num_bon=num_bon,
                serveur_version=serveur_version,
                base_version=pb.base_version,
                serveur_updated_at=_iso(existing.updated_at)))
            continue

        # ── Cas 3 : pas de conflit (ou force) -> on ecrase + version++ ──────
        for k, v in data.items():
            if k in cols_valides and k not in cols_exclues and k != "id":
                setattr(existing, k, v)
        if req.device:
            existing.sync_device = req.device
        existing.sync_state = "atelier"
        existing.version = serveur_version + 1
        res.appliques += 1

    db.commit()
    return res
