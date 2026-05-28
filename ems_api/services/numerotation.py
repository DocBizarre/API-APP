"""Service de numérotation automatique des bons et garanties.

Supporte un préfixe d'appareil optionnel pour la synchronisation hors-ligne :
  - Au bureau (device_prefix vide)      : BON-2026-0008
  - Sur tablette (device_prefix="T1")   : BON-T1-2026-0008

Le compteur est INDEPENDANT par appareil : chaque device compte ses propres
numéros, ce qui garantit l'absence de collision entre le serveur et les
tablettes (ou entre tablettes) lors de la synchronisation.
"""
from datetime import datetime
from sqlalchemy.orm import Session

from ..models.intervention import Intervention
from ..models.garantie import Garantie
from ..models.amelioration import Amelioration


def _prochain_numero(db: Session, model, colonne, type_prefix: str,
                     device_prefix: str = "") -> str:
    """
    Génère le prochain numéro séquentiel pour un type donné.

    type_prefix   : "BON", "GAR", "AME"
    device_prefix : "" (bureau) ou identifiant tablette comme "T1"
    Format résultat :
      - sans device : BON-2026-0008
      - avec device : BON-T1-2026-0008
    """
    annee = datetime.now().year
    dev = (device_prefix or "").strip()
    if dev:
        prefixe = f"{type_prefix}-{dev}-{annee}-"
    else:
        prefixe = f"{type_prefix}-{annee}-"

    col = getattr(model, colonne)
    dernier = (
        db.query(model)
        .filter(col.like(f"{prefixe}%"))
        .order_by(col.desc())
        .first()
    )
    if dernier:
        try:
            num = int(getattr(dernier, colonne).split("-")[-1]) + 1
        except (ValueError, AttributeError):
            num = 1
    else:
        num = 1
    return f"{prefixe}{num:04d}"


def next_num_bon(db: Session, device_prefix: str = "") -> str:
    """Génère le prochain numéro de bon : BON-AAAA-XXXX (ou BON-T1-AAAA-XXXX)."""
    return _prochain_numero(db, Intervention, "num_bon", "BON", device_prefix)


def next_num_garantie(db: Session, device_prefix: str = "") -> str:
    """Génère le prochain numéro de garantie : GAR-AAAA-XXXX."""
    return _prochain_numero(db, Garantie, "num_ems", "GAR", device_prefix)


def next_num_amelioration(db: Session, device_prefix: str = "") -> str:
    """Génère le prochain numéro de ticket : AME-AAAA-XXXX."""
    return _prochain_numero(db, Amelioration, "num_ticket", "AME", device_prefix)
