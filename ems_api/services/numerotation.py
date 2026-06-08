"""Service de numérotation automatique des bons et garanties.

Supporte un préfixe d'appareil optionnel pour la synchronisation hors-ligne :
  - Au bureau (device_prefix vide)      : BON-2026-0008
  - Sur tablette (device_prefix="T1")   : BON-T1-2026-0008

Garantie d'unicité même après suppression :
  Un "high water mark" (HWM) est stocké dans la table config sous la clé
  "hwm:<prefixe>". Le prochain numéro est toujours max(db_max, hwm) + 1,
  ce qui assure qu'un numéro supprimé ne soit jamais réattribué.
"""
from datetime import datetime
from sqlalchemy.orm import Session

from ..models.intervention import Intervention
from ..models.garantie import Garantie
from ..models.amelioration import Amelioration


def _prochain_numero(db: Session, model, colonne: str, type_prefix: str,
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
    prefixe = f"{type_prefix}-{dev}-{annee}-" if dev else f"{type_prefix}-{annee}-"

    col = getattr(model, colonne)

    # ── 1. Max des enregistrements existants ──────────────────────────────────
    dernier_db = (
        db.query(model)
        .filter(col.like(f"{prefixe}%"))
        .order_by(col.desc())
        .first()
    )
    num_db = 0
    if dernier_db:
        try:
            num_db = int(getattr(dernier_db, colonne).split("-")[-1])
        except (ValueError, AttributeError):
            num_db = 0

    # ── 2. High water mark stocké en config (résiste aux suppressions) ────────
    from ..models.configurations import Config
    hwm_key = f"hwm:{prefixe}"
    cfg = db.query(Config).filter(Config.cle == hwm_key).first()
    num_hwm = 0
    if cfg and cfg.valeur:
        try:
            num_hwm = int(cfg.valeur)
        except ValueError:
            num_hwm = 0

    # ── 3. Prochain numéro = max des deux sources + 1 ─────────────────────────
    num = max(num_db, num_hwm) + 1
    new_num_str = f"{prefixe}{num:04d}"

    # ── 4. Mise à jour du HWM ─────────────────────────────────────────────────
    if cfg:
        cfg.valeur = str(num)
    else:
        db.add(Config(cle=hwm_key, valeur=str(num)))
    db.commit()

    return new_num_str


def next_num_bon(db: Session, device_prefix: str = "") -> str:
    """Génère le prochain numéro de bon : BON-AAAA-XXXX (ou BON-T1-AAAA-XXXX)."""
    return _prochain_numero(db, Intervention, "num_bon", "BON", device_prefix)


def next_num_garantie(db: Session, device_prefix: str = "") -> str:
    """Génère le prochain numéro de garantie : GAR-AAAA-XXXX."""
    return _prochain_numero(db, Garantie, "num_ems", "GAR", device_prefix)


def next_num_amelioration(db: Session, device_prefix: str = "") -> str:
    """Génère le prochain numéro de ticket : AME-AAAA-XXXX."""
    return _prochain_numero(db, Amelioration, "num_ticket", "AME", device_prefix)
