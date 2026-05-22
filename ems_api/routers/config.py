"""Router /config — préférences dashboard stockées dans la table config."""
import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
 
from ..database import get_db
 
router = APIRouter(prefix="/config", tags=["config"])
 
# Clés utilisées dans la table config
_KEY_WIDGETS = "dashboard_widgets"
_KEY_CARDS   = "dashboard_cards"
 
# Valeurs par défaut
_DEFAULT_WIDGETS = [
    "stats_cards", "interventions_urgentes", "activite_recente",
    "garanties_expirantes", "charge_technicien", "repartition_type",
    "non_notifies", "classifications"
]
_DEFAULT_CARDS = [
    "en_cours", "clos", "total", "urgentes", "critiques",
    "garantie", "facturables", "clients", "moteurs", "techniciens"
]
 
 
def _get_config(db: Session, key: str, default) -> list:
    row = db.execute(
        text("SELECT valeur FROM config WHERE cle = :k"), {"k": key}
    ).fetchone()
    if row:
        try:
            return json.loads(row[0])
        except (ValueError, TypeError):
            pass
    return default
 
 
def _set_config(db: Session, key: str, value: list) -> None:
    existing = db.execute(
        text("SELECT cle FROM config WHERE cle = :k"), {"k": key}
    ).fetchone()
    if existing:
        db.execute(
            text("UPDATE config SET valeur = :v WHERE cle = :k"),
            {"k": key, "v": json.dumps(value, ensure_ascii=False)}
        )
    else:
        db.execute(
            text("INSERT INTO config (cle, valeur) VALUES (:k, :v)"),
            {"k": key, "v": json.dumps(value, ensure_ascii=False)}
        )
    db.commit()
 
 
# ─── Widgets ─────────────────────────────────────────────────────────────────
 
@router.get("/dashboard-widgets")
def get_dashboard_widgets(db: Session = Depends(get_db)):
    return _get_config(db, _KEY_WIDGETS, _DEFAULT_WIDGETS)
 
 
@router.post("/dashboard-widgets")
def set_dashboard_widgets(widgets: list, db: Session = Depends(get_db)):
    _set_config(db, _KEY_WIDGETS, widgets)
    return {"ok": True}
 
 
# ─── Cartes statistiques ──────────────────────────────────────────────────────
 
@router.get("/dashboard-cards")
def get_dashboard_cards(db: Session = Depends(get_db)):
    return _get_config(db, _KEY_CARDS, _DEFAULT_CARDS)
 
 
@router.post("/dashboard-cards")
def set_dashboard_cards(cards: list, db: Session = Depends(get_db)):
    _set_config(db, _KEY_CARDS, cards)
    return {"ok": True}