"""
═══════════════════════════════════════════════════════════════════════════════
  Sauvegarde automatique de la base de données EMS
═══════════════════════════════════════════════════════════════════════════════

Crée une copie horodatée de ems.db dans data/backups/.
Conserve les N derniers jours (par défaut 30) et supprime les plus vieux.

Usage :
    python -m ems_api.backup            # sauvegarde unique
    python -m ems_api.backup --schedule # lance un thread qui sauvegarde chaque jour

À intégrer dans le démarrage de l'API pour automatiser.
═══════════════════════════════════════════════════════════════════════════════
"""
import logging
import shutil
import sys
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path

from .config import settings

logger = logging.getLogger(__name__)
JOURS_RETENTION = 30


def sauvegarder() -> Path:
    """Copie la base actuelle vers data/backups/ems_YYYY-MM-DD_HHMM.db."""
    if not settings.DB_PATH.is_file():
        logger.warning("Base introuvable : %s", settings.DB_PATH)
        return None
    backups_dir = settings.DATA_DIR / "backups"
    backups_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    dest = backups_dir / f"ems_{timestamp}.db"
    shutil.copy2(settings.DB_PATH, dest)
    taille_mo = dest.stat().st_size / (1024 * 1024)
    logger.info("Sauvegarde : %s (%.2f Mo)", dest.name, taille_mo)
    nettoyer_anciennes()
    return dest


def nettoyer_anciennes():
    """Supprime les sauvegardes plus vieilles que JOURS_RETENTION."""
    backups_dir = settings.DATA_DIR / "backups"
    if not backups_dir.is_dir():
        return
    seuil = datetime.now() - timedelta(days=JOURS_RETENTION)
    n_supprimees = 0
    for f in backups_dir.glob("ems_*.db"):
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        if mtime < seuil:
            f.unlink()
            n_supprimees += 1
    if n_supprimees:
        logger.info("%d ancienne(s) sauvegarde(s) supprimée(s)", n_supprimees)


def planifier_quotidien():
    """Lance un thread qui sauvegarde chaque jour à 2h du matin."""
    def boucle():
        while True:
            now = datetime.now()
            cible = now.replace(hour=2, minute=0, second=0, microsecond=0)
            if cible <= now:
                cible += timedelta(days=1)
            attente = (cible - now).total_seconds()
            time.sleep(attente)
            try:
                sauvegarder()
            except Exception as e:
                logger.error("Échec sauvegarde planifiée : %s", e)
    th = threading.Thread(target=boucle, daemon=True, name="ems-backup")
    th.start()
    logger.info("Sauvegarde quotidienne planifiée (2h00 du matin)")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    if "--schedule" in sys.argv:
        planifier_quotidien()
        sauvegarder()
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            print("\nArrêt.")
    else:
        sauvegarder()
