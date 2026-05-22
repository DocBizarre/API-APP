"""Service de numérotation automatique des bons et garanties."""
from datetime import datetime
from sqlalchemy.orm import Session
 
from ..models.intervention import Intervention
from ..models.garantie import Garantie
from ..models.amelioration import Amelioration
 
 
def next_num_bon(db: Session) -> str:
    """Génère le prochain numéro de bon : BON-AAAA-XXXX."""
    annee = datetime.now().year
    prefixe = f"BON-{annee}-"
    dernier = (
        db.query(Intervention)
        .filter(Intervention.num_bon.like(f"{prefixe}%"))
        .order_by(Intervention.num_bon.desc())
        .first()
    )
    if dernier:
        try:
            num = int(dernier.num_bon.split("-")[-1]) + 1
        except ValueError:
            num = 1
    else:
        num = 1
    return f"{prefixe}{num:04d}"
 
 
def next_num_garantie(db: Session) -> str:
    """Génère le prochain numéro de garantie : GAR-AAAA-XXXX."""
    annee = datetime.now().year
    prefixe = f"GAR-{annee}-"
    dernier = (
        db.query(Garantie)
        .filter(Garantie.num_ems.like(f"{prefixe}%"))
        .order_by(Garantie.num_ems.desc())
        .first()
    )
    if dernier:
        try:
            num = int(dernier.num_ems.split("-")[-1]) + 1
        except ValueError:
            num = 1
    else:
        num = 1
    return f"{prefixe}{num:04d}"
 
 
def next_num_amelioration(db: Session) -> str:
    """Génère le prochain numéro de ticket : AME-AAAA-XXXX."""
    annee = datetime.now().year
    prefixe = f"AME-{annee}-"
    dernier = (
        db.query(Amelioration)
        .filter(Amelioration.num_ticket.like(f"{prefixe}%"))
        .order_by(Amelioration.num_ticket.desc())
        .first()
    )
    if dernier:
        try:
            num = int(dernier.num_ticket.split("-")[-1]) + 1
        except ValueError:
            num = 1
    else:
        num = 1
    return f"{prefixe}{num:04d}"