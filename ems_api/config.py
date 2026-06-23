"""
Configuration centrale de l'API EMS.
Priorité : config.ini [files] data_dir  >  env EMS_DATA_DIR  >  ./data
"""
import os
from configparser import ConfigParser
from pathlib import Path


def _detect_data_dir(base: Path) -> Path:
    """Lit data_dir depuis config.ini (à côté du repo), sinon env var, sinon défaut."""
    for ini in (base.parent / "config.ini", base / "config.ini"):
        if ini.is_file():
            try:
                cfg = ConfigParser()
                cfg.read(str(ini), encoding="utf-8")
                d = cfg.get("files", "data_dir", fallback="").strip()
                if d:
                    return Path(d)
            except Exception:
                pass
    return Path(os.environ.get("EMS_DATA_DIR", str(base / "data")))


class Settings:
    # ─── Chemins ─────────────────────────────────────────────────────────
    BASE_DIR: Path = Path(__file__).resolve().parent
    DATA_DIR: Path = _detect_data_dir(BASE_DIR)
    DB_PATH: Path = DATA_DIR / "ems.db"
    DOSSIERS_DIR: Path = DATA_DIR / "dossiers"
    GARANTIES_DIR: Path = DATA_DIR / "garanties"
    AMELIORATIONS_DIR: Path = DATA_DIR / "ameliorations"

    # ─── Serveur ─────────────────────────────────────────────────────────
    HOST: str = os.environ.get("EMS_API_HOST", "0.0.0.0")
    PORT: int = int(os.environ.get("EMS_API_PORT", "8765"))

    # ─── Identité de l'appareil (synchronisation hors-ligne) ────────────
    # Vide = serveur central (numeros BON-2026-XXXX)
    # "T1", "T2"... = tablette terrain (numeros BON-T1-2026-XXXX)
    DEVICE_PREFIX: str = os.environ.get("EMS_DEVICE_PREFIX", "")

    # ─── CORS (utile si UI web plus tard) ───────────────────────────────
    CORS_ORIGINS: list = os.environ.get(
        "EMS_CORS", "*").split(",")

    # ─── Auth (à activer plus tard si déploiement réseau) ───────────────
    API_KEY: str = os.environ.get("EMS_API_KEY", "")  # vide = pas d'auth
    AUTH_ENABLED: bool = bool(API_KEY)

    # ─── Entreprise (utilisé par le générateur de bons HTML/PDF) ────────
    ENTREPRISE = {
        "nom": "Emeraude Moteurs Systèmes",
        "adresse_1": "9 Rue d'Armorique – 35540 Miniac Morvan",
        "adresse_2": "",
        "tel": "02.99.19.01.99",
        "fax": "",
        "email": "service.technique@emeraudemoteurs.com",
        "siret": "431 976 729 00027",
        "tva": "FR 14 431 976 729",
        "site": "www.emeraudemoteurs.com",
    }

    @classmethod
    def init_dirs(cls):
        """Crée les dossiers nécessaires s'ils n'existent pas."""
        for d in (cls.DATA_DIR, cls.DOSSIERS_DIR,
                  cls.GARANTIES_DIR, cls.AMELIORATIONS_DIR):
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
