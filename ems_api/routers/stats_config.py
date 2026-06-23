"""Endpoints REST pour les statistiques et la config du tableau de bord."""
import json
from typing import List, Dict, Any
from collections import Counter, defaultdict

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Intervention, Client, Moteur, Technicien, Garantie
from ..models.configurations import Config


router_stats = APIRouter(prefix="/stats", tags=["stats"])
router_config = APIRouter(prefix="/config", tags=["config"])


# ═════════════════════════════════════════════════════════════════════════════
#   STATISTIQUES
# ═════════════════════════════════════════════════════════════════════════════

@router_stats.get("")
def stats(db: Session = Depends(get_db)) -> Dict[str, int]:
    """Statistiques globales — TOUTES les clés attendues par le code Tkinter."""
    inv_all = db.query(Intervention).all()
    total = len(inv_all)

    par_statut = Counter()
    for i in inv_all:
        if i.statut:
            par_statut[i.statut] += 1

    urgentes_en_cours = sum(1 for i in inv_all
                             if i.statut == "En cours"
                             and i.urgence == "Urgente")
    critiques_en_cours = sum(1 for i in inv_all
                              if i.statut == "En cours"
                              and i.urgence == "Critique")
    sous_garantie = sum(1 for i in inv_all if i.garantie_intervention)
    facturables = sum(1 for i in inv_all if i.facturable)
    internes = sum(1 for i in inv_all if i.interne)
    non_notifies = sum(1 for i in inv_all
                        if i.statut == "En cours"
                        and (not i.client_notifie or not i.tech_notifie))

    # Volumes globaux
    nb_clients = db.query(Client).count()
    nb_moteurs = db.query(Moteur).count()
    nb_techniciens = db.query(Technicien).count()

    res = {
        "Total":        total,
        "En cours":     par_statut.get("En cours", 0),
        "Date à programmer": par_statut.get("Date à programmer", 0),
        "Facturé":      par_statut.get("Facturé", 0),
        "À facturer":   par_statut.get("À facturer", 0),
        "Clos":         par_statut.get("Clos", 0),
        "Urgentes":     urgentes_en_cours,
        "Critiques":    critiques_en_cours,
        "Garantie":     sous_garantie,
        "Facturables":  facturables,
        "Internes":     internes,
        "Non notifiés": non_notifies,
        # Volumes globaux (clés en minuscules — attendues par main.py)
        "clients":      nb_clients,
        "moteurs":      nb_moteurs,
        "techniciens":  nb_techniciens,
    }
    # Ajoute aussi les autres statuts vus, sans écraser
    for s, n in par_statut.items():
        res.setdefault(s, n)
    return res


@router_stats.get("/par-technicien")
def stats_par_technicien(db: Session = Depends(get_db)) -> List[Dict]:
    """Stats par technicien : {technicien, en_cours, a_facturer, facture, clos, total}."""
    par_tech = defaultdict(lambda: {"en_cours": 0, "a_facturer": 0,
                                      "facture": 0, "clos": 0, "total": 0})
    for i in db.query(Intervention).all():
        if not i.technicien:
            continue
        for t in str(i.technicien).split(","):
            t = t.strip()
            if not t:
                continue
            par_tech[t]["total"] += 1
            statut = (i.statut or "").lower()
            if statut == "en cours":
                par_tech[t]["en_cours"] += 1
            elif statut == "à facturer":
                par_tech[t]["a_facturer"] += 1
            elif statut == "facturé":
                par_tech[t]["facture"] += 1
            elif statut == "clos":
                par_tech[t]["clos"] += 1
    out = [{"technicien": t, **stats} for t, stats in par_tech.items()]
    out.sort(key=lambda r: r["en_cours"], reverse=True)
    return out


@router_stats.get("/par-type")
def stats_par_type(db: Session = Depends(get_db)) -> List[Dict]:
    """Stats par type d'intervention : {type, en_cours, total}."""
    par_type = defaultdict(lambda: {"en_cours": 0, "total": 0})
    for i in db.query(Intervention).all():
        t = i.type_intervention or "(Non spécifié)"
        par_type[t]["total"] += 1
        if (i.statut or "").lower() == "en cours":
            par_type[t]["en_cours"] += 1
    out = [{"type": t, **stats} for t, stats in par_type.items()]
    out.sort(key=lambda r: r["total"], reverse=True)
    return out


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
            "type_intervention": inv.type_intervention or "",
            "statut": inv.statut or "",
            "urgence": inv.urgence or "",
            "technicien": inv.technicien or "",
            "date_creation": inv.date_creation or "",
            "created_at": inv.created_at.isoformat() if inv.created_at else "",
            "updated_at": inv.updated_at.isoformat() if inv.updated_at else "",
            "client_nom": inv.client.nom if inv.client else "",
            "moteur_serie": inv.moteur.num_serie if inv.moteur else "",
            "navire": inv.moteur.navire if inv.moteur else "",
        })
    return out


# ═════════════════════════════════════════════════════════════════════════════
#   CONFIG : Dashboard widgets / cards (raccourcis explicites)
# ═════════════════════════════════════════════════════════════════════════════

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
        ["stats_cards", "urgentes", "a_programmer", "activite_recente",
         "garantie_expirante", "par_technicien", "non_notifies", "par_type"])


@router_config.post("/dashboard-widgets")
def set_dashboard_widgets(widgets: List[str] = Body(...),
                           db: Session = Depends(get_db)):
    _set_list_config(db, "dashboard_widgets", widgets)
    return {"ok": True}


@router_config.get("/dashboard-cards", response_model=List[str])
def get_dashboard_cards(db: Session = Depends(get_db)) -> List[str]:
    return _get_list_config(db, "dashboard_cards",
        ["En cours", "Date à programmer", "Facturé", "Clos", "Total", "Urgentes"])


@router_config.post("/dashboard-cards")
def set_dashboard_cards(cards: List[str] = Body(...),
                         db: Session = Depends(get_db)):
    _set_list_config(db, "dashboard_cards", cards)
    return {"ok": True}


# ═════════════════════════════════════════════════════════════════════════════
#   CONFIG : clé/valeur générique
# ═════════════════════════════════════════════════════════════════════════════

@router_config.get("/{cle}")
def get_config(cle: str, db: Session = Depends(get_db)):
    c = db.query(Config).filter(Config.cle == cle).first()
    if not c:
        return {"cle": cle, "valeur": None}
    return {"cle": c.cle, "valeur": c.valeur}


@router_config.post("/{cle}")
def set_config(cle: str, valeur: Any = Body(...),
                db: Session = Depends(get_db)):
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
