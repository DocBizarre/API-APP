"""Service de numérotation automatique des bons et garanties.

Supporte un préfixe d'appareil optionnel pour la synchronisation hors-ligne :
  - Au bureau (device_prefix vide)      : BON-2026-0008
  - Sur tablette (device_prefix="T1")   : BON-T1-2026-0008

Garantie d'unicité même après suppression :
  Un "high water mark" (HWM) est stocké dans la table config sous la clé
  "hwm:<prefixe>". Le prochain numéro est toujours max(db_max, hwm) + 1,
  ce qui assure qu'un numéro supprimé ne soit jamais réattribué.

Concurrence :
  SQLite : un verrou threading (_num_lock) serialise les appels dans le même
  processus. Si la DB est migrée vers PostgreSQL, remplacer le verrou par un
  SELECT FOR UPDATE sur la ligne HWM en config.
"""
import re
import threading
from datetime import datetime
from sqlalchemy.orm import Session

from ..models.intervention import Intervention
from ..models.garantie import Garantie
from ..models.amelioration import Amelioration
from ..models.affaire import Affaire
from ..models.bon_commande import BonCommande
from ..models.devis import Devis

# Serialize sequence generation within a single process (SQLite safety).
_num_lock = threading.Lock()


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
    with _num_lock:
        return _prochain_numero_locked(db, model, colonne, type_prefix, device_prefix)


def _prochain_numero_locked(db: Session, model, colonne: str, type_prefix: str,
                             device_prefix: str = "") -> str:
    """Corps de _prochain_numero exécuté sous _num_lock."""
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


def code_from_num_affaire(num_affaire: str) -> str:
    """Extrait le code affaire court AAAANNNN (ex. "20260013") d'un num_affaire.

    Le num_affaire complet porte un préfixe variable selon l'origine
    (AMOT20260013, AFF-2026-0009, ...) ; le champ moteurs.code_affaire ne
    stocke que la partie numérique AAAANNNN, format legacy hérité des
    imports CSV. Repli sur la chaîne d'origine si elle ne contient pas
    8 chiffres exploitables.
    """
    digits = re.sub(r"\D", "", num_affaire or "")
    return digits[-8:] if len(digits) >= 8 else (num_affaire or "")


def next_num_bon(db: Session, device_prefix: str = "") -> str:
    """Génère le prochain numéro de bon : BON-AAAA-XXXX (ou BON-T1-AAAA-XXXX)."""
    return _prochain_numero(db, Intervention, "num_bon", "BON", device_prefix)


def next_num_garantie(db: Session, device_prefix: str = "") -> str:
    """Génère le prochain numéro de garantie : GAR-AAAA-XXXX."""
    return _prochain_numero(db, Garantie, "num_ems", "GAR", device_prefix)


def next_num_amelioration(db: Session, device_prefix: str = "") -> str:
    """Génère le prochain numéro de ticket : AME-AAAA-XXXX."""
    return _prochain_numero(db, Amelioration, "num_ticket", "AME", device_prefix)


def next_num_bon_commande(db: Session, device_prefix: str = "") -> str:
    """Génère le prochain numéro de bon de commande : BC-AAAA-XXXX."""
    return _prochain_numero(db, BonCommande, "num_bc", "BC", device_prefix)


def next_num_devis(db: Session, device_prefix: str = "") -> str:
    """Génère le prochain numéro de devis : DEV-AAAA-XXXX."""
    return _prochain_numero(db, Devis, "num_devis", "DEV", device_prefix)


def next_num_affaire(db: Session, device_prefix: str = "") -> str:
    """Génère le prochain numéro d'affaire : AMOTYYYYNNNN (ex. AMOT20260001)."""
    with _num_lock:
        annee = datetime.now().year
        prefixe = f"AMOT{annee}"
        col = Affaire.num_affaire

        dernier_db = (
            db.query(Affaire)
            .filter(col.like(f"{prefixe}%"))
            .order_by(col.desc())
            .first()
        )
        num_db = 0
        if dernier_db:
            try:
                num_db = int(dernier_db.num_affaire[len(prefixe):])
            except (ValueError, AttributeError):
                num_db = 0

        from ..models.configurations import Config
        hwm_key = f"hwm:{prefixe}"
        cfg = db.query(Config).filter(Config.cle == hwm_key).first()
        num_hwm = 0
        if cfg and cfg.valeur:
            try:
                num_hwm = int(cfg.valeur)
            except ValueError:
                num_hwm = 0

        num = max(num_db, num_hwm) + 1
        new_num_str = f"{prefixe}{num:04d}"

        if cfg:
            cfg.valeur = str(num)
        else:
            db.add(Config(cle=hwm_key, valeur=str(num)))
        db.commit()
        return new_num_str
