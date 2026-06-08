"""Configuration du logging pour l'API EMS."""
import logging
import logging.handlers
from pathlib import Path

from .config import settings


def setup_logging():
    """Configure un logger racine avec sortie console + fichier rotatif."""
    log_dir = settings.DATA_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "ems.log"

    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Éviter d'ajouter les handlers plusieurs fois (rechargement uvicorn)
    if root.handlers:
        return

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    file_h = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_h.setFormatter(fmt)
    root.addHandler(file_h)
