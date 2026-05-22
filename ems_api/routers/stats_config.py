"""Endpoints REST pour les statistiques globales et la config du tableau de bord."""
import json
from typing import List, Dict, Any
from collections import Counter

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from ..database import get_db
from ..models import Intervention, Garantie, Client, Moteur
from ..models.configurations import Config


router_stats = APIRouter(prefix="/stats", tags=["stats"])
router_config = APIRouter(prefix="/config", tags=["config"])


# ─── Stats ──────────────────────────────────────────────────────────────────
@router_stats.get("")
def stats(db: Session = Depends(get_db)) -> Dict[str, int]:
    """Statistiques pour les cartes du tableau de bord."""
    total = db.query(Intervention).count()
    urgentes = db.query(Intervention).filter(
        Intervention.urgence.in_(("Urgente", "Critique")),
        Intervention.statut == "En cours").count()
    par_statut = Counter()
    for r in db.query(Intervention.statut).all():
        if r[0]:
            par_statut[r[0]] += 1
    res = {
        "Total": total,
        "Urgentes": urgentes,
        "En cours": par_statut.get("En cours", 0),
        "Facturé": par_statut.get("Facturé", 0),
        "À facturer": par_statut.get("À facturer", 0),
        "Clos": par_statut.get("Clos", 0),
    }
    # Ajoute tous les statuts vus dans la base (au cas où d'autres existent)
    for s, n in par_statut.items():
        res.setdefault(s, n)
    return res


@router_stats.get("/par-technicien")
def stats_par_technicien(db: Session = Depends(get_db)) -> List[Dict]:
    """Compte des interventions actives par technicien."""
    c = Counter()
    for r in db.query(Intervention.technicien).filter(
            Intervention.statut == "En cours").all():
        if not r[0]:
            continue
        # Le champ peut contenir plusieurs techniciens "A, B, C"
        for t in str(r[0]).split(","):
            t = t.strip()
            if t:
                c[t] += 1
    return [{"technicien": t, "count": n}
            for t, n in c.most_common()]


@router_stats.get("/par-type")
def stats_par_type(db: Session = Depends(get_db)) -> List[Dict]:
    """Compte des interventions par type."""
    c = Counter()
    for r in db.query(Intervention.type_intervention).all():
        if r[0]:
            c[r[0]] += 1
    return [{"type": t, "count": n} for t, n in c.most_common()]


@router_stats.get("/activite-recente")
def activite_recente(limit: int = Query(20, ge=1, le=200),
                      db: Session = Depends(get_db)) -> List[Dict]:
    """Dernières interventions créées."""
    q = (db.query(Intervention)
         .order_by(Intervention.created_at.desc())
         .limit(limit))
    out = []
    for inv in q.all():
        out.append({
            "id": inv.id,
            "num_bon": inv.num_bon,
            "type_intervention": inv.type_intervention,
            "statut": inv.statut,
            "urgence": inv.urgence,
            "technicien": inv.technicien,
            "date_creation": inv.date_creation,
            "created_at": inv.created_at.isoformat() if inv.created_at else None,
            "client_nom": inv.client.nom if inv.client else None,
            "moteur_serie": inv.moteur.num_serie if inv.moteur else None,
        })
    return out


# ─── Dashboard widgets / cards (raccourcis) ─────────────────────────────────
# IMPORTANT : ces routes doivent être déclarées AVANT la route /{cle}
# sinon dashboard-widgets serait capturé comme une clé générique.
def _get_list_config(db: Session, cle: str, defaut: List[str]) -> List[str]:
    c = db.query(Config).filter(Config.cle == cle).first()
    if not c or not c.valeur:
        return defaut
    try:
        v = json.loads(c.valeur)
        return v if isinstance(v, list) else defaut
    except (ValueError, TypeError):
        return defaut


def _set_list_config(db: Session, cle: str, val: List[str]):
    j = json.dumps(val, ensure_ascii=False)
    c = db.query(Config).filter(Config.cle == cle).first()
    if c:
        c.valeur = j
    else:
        db.add(Config(cle=cle, valeur=j))
    db.commit()


@router_config.get("/dashboard-widgets", response_model=List[str])
def get_dashboard_widgets(db: Session = Depends(get_db)) -> List[str]:
    return _get_list_config(db, "dashboard_widgets",
        ["stats_cards", "urgentes", "activite_recente",
         "garantie_expirante", "par_technicien", "non_notifies", "par_type"])


@router_config.post("/dashboard-widgets")
def set_dashboard_widgets(widgets: List[str] = Body(...),
                           db: Session = Depends(get_db)):
    _set_list_config(db, "dashboard_widgets", widgets)
    return {"ok": True}


@router_config.get("/dashboard-cards", response_model=List[str])
def get_dashboard_cards(db: Session = Depends(get_db)) -> List[str]:
    return _get_list_config(db, "dashboard_cards",
        ["En cours", "Facturé", "Clos", "Total", "Urgentes"])


@router_config.post("/dashboard-cards")
def set_dashboard_cards(cards: List[str] = Body(...),
                         db: Session = Depends(get_db)):
    _set_list_config(db, "dashboard_cards", cards)
    return {"ok": True}


# ─── Config (clé/valeur générique) ──────────────────────────────────────────
@router_config.get("/{cle}")
def get_config(cle: str, db: Session = Depends(get_db)):
    c = db.query(Config).filter(Config.cle == cle).first()
    if not c:
        return {"cle": cle, "valeur": None}
    return {"cle": c.cle, "valeur": c.valeur}


@router_config.post("/{cle}")
def set_config(cle: str, valeur: Any = Body(...),
                db: Session = Depends(get_db)):
    """Stocke n'importe quelle valeur sérialisable en JSON."""
    val = valeur if isinstance(valeur, str) else json.dumps(valeur,
                                                              ensure_ascii=False)
    c = db.query(Config).filter(Config.cle == cle).first()
    if c:
        c.valeur = val
    else:
        c = Config(cle=cle, valeur=val)
        db.add(c)
    db.commit()
    return {"cle": cle, "valeur": val}
