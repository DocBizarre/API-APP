"""
Import / export de bons d'intervention au format .ems (JSON).

Format du bundle :
{
  "ems_version": "1.0",
  "exported_at": "<ISO>",
  "intervention": { ...tous les champs de l'intervention... },
  "refs": {
    "clients":     [...],   # liste complète pour les dropdowns hors-ligne
    "moteurs":     [...],
    "techniciens": [...],
    "types":       [...]
  },
  "offline_edits":    null | { ...données modifiées hors-ligne... },
  "offline_edited_at": null | "<ISO>"
}
"""
import json
from datetime import datetime
from pathlib import Path

EMS_VERSION = "1.0"


def build_bundle(inv: dict, clients: list, moteurs: list,
                 techniciens: list, types: list) -> dict:
    """Construit le bundle exportable depuis les données API."""
    return {
        "ems_version": EMS_VERSION,
        "exported_at": datetime.now().isoformat(),
        "intervention": dict(inv),
        "refs": {
            "clients":     clients,
            "moteurs":     moteurs,
            "techniciens": techniciens,
            "types":       types,
        },
        "offline_edits":     None,
        "offline_edited_at": None,
    }


def save_bundle(bundle: dict, path) -> None:
    """Écrit le bundle au format JSON dans un fichier .ems."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False, indent=2)


def load_bundle(path) -> dict:
    """Charge et valide un fichier .ems. Lève ValueError si invalide."""
    with open(path, "r", encoding="utf-8") as f:
        bundle = json.load(f)
    if "intervention" not in bundle:
        raise ValueError("Fichier .ems invalide : champ 'intervention' manquant.")
    return bundle


def apply_offline_edits(bundle: dict, edits: dict, path) -> None:
    """Ajoute les modifications hors-ligne dans le bundle et réécrit le fichier."""
    bundle["offline_edits"] = edits
    bundle["offline_edited_at"] = datetime.now().isoformat()
    save_bundle(bundle, path)


def get_data(bundle: dict) -> dict:
    """Retourne les données effectives : offline_edits si présent, sinon intervention."""
    return bundle.get("offline_edits") or bundle["intervention"]
