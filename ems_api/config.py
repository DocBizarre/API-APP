"""
Configuration centrale de l'API EMS.
Toutes les valeurs peuvent être surchargées via variables d'environnement.
"""
import os
from pathlib import Path


class Settings:
    # ─── Chemins ─────────────────────────────────────────────────────────
    BASE_DIR: Path = Path(__file__).resolve().parent
    DATA_DIR: Path = Path(os.environ.get("EMS_DATA_DIR",
                                          str(BASE_DIR / "data")))
    DB_PATH: Path = DATA_DIR / "ems.db"
    DOSSIERS_DIR: Path = DATA_DIR / "dossiers"
    GARANTIES_DIR: Path = DATA_DIR / "garanties"
    AMELIORATIONS_DIR: Path = DATA_DIR / "ameliorations"

    # ─── Serveur ─────────────────────────────────────────────────────────
    HOST: str = os.environ.get("EMS_API_HOST", "127.0.0.1")
    PORT: int = int(os.environ.get("EMS_API_PORT", "8765"))

    # ─── CORS (utile si UI web plus tard) ───────────────────────────────
    CORS_ORIGINS: list = os.environ.get(
        "EMS_CORS", "*").split(",")

    # ─── Auth (à activer plus tard si déploiement réseau) ───────────────
    API_KEY: str = os.environ.get("EMS_API_KEY", "")  # vide = pas d'auth
    AUTH_ENABLED: bool = bool(API_KEY)

    # ─── Entreprise (utilisé par le générateur de bons HTML/PDF) ────────
    ENTREPRISE = {
        "nom": "Emeraude Moteurs Systèmes",
        "adresse_1": "9bis avenue Louis Martin – 35400 Saint Malo",
        "adresse_2": "9 Rue d'Armorique – 35540 Miniac Morvan",
        "tel": "02.99.19.01.99",
        "fax": "02.99.81.11.75",
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
