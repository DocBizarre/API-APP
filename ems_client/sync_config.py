"""
Configuration de synchronisation côté client (tablette ou poste).

Stocke dans un fichier JSON local :
  - server_url   : adresse de l'API centrale (serveur atelier)
  - device_id    : identifiant de cet appareil ("T1", "T2"...) ; vide = poste bureau
  - local_url    : adresse de l'API locale (cache tablette), defaut 127.0.0.1:8765

Le fichier sync_config.json est cree a cote de ce module au premier lancement
avec des valeurs par defaut, puis modifiable par l'utilisateur (ecran parametres
ou edition manuelle).
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict


CONFIG_PATH = Path(__file__).resolve().parent / "sync_config.json"

DEFAULTS: Dict[str, str] = {
    "server_url": "http://192.168.1.50:8765",   # serveur atelier (a adapter)
    "local_url":  "http://127.0.0.1:8765",       # cache local de la tablette
    "device_id":  "",                            # "" = bureau ; "T1" = tablette 1
}


def _read_raw() -> Dict[str, str]:
    if CONFIG_PATH.is_file():
        try:
            # utf-8-sig : tolere un BOM eventuel (Out-File PowerShell en ajoute un)
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def load() -> Dict[str, str]:
    """Retourne la config complete (valeurs par defaut + surcharges du fichier)."""
    cfg = dict(DEFAULTS)
    cfg.update(_read_raw())
    return cfg


def save(cfg: Dict[str, str]) -> None:
    """Sauvegarde la config (fusion avec l'existant)."""
    current = load()
    current.update({k: v for k, v in cfg.items() if k in DEFAULTS})
    CONFIG_PATH.write_text(
        json.dumps(current, indent=2, ensure_ascii=False),
        encoding="utf-8")   # write_text en utf-8 = SANS BOM

def get(key: str, default: str = "") -> str:
    return load().get(key, default)


def set_value(key: str, value: str) -> None:
    if key in DEFAULTS:
        save({key: value})


# Raccourcis pratiques
def server_url() -> str:
    return load()["server_url"].rstrip("/")


def local_url() -> str:
    return load()["local_url"].rstrip("/")


def device_id() -> str:
    return load().get("device_id", "")


def ensure_config_file() -> Path:
    """Cree le fichier de config avec les valeurs par defaut s'il n'existe pas."""
    if not CONFIG_PATH.is_file():
        save(dict(DEFAULTS))
    return CONFIG_PATH
