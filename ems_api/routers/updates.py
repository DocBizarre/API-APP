"""
Endpoint de vérification de mise à jour.
Aucune authentification requise — accessible à tous les clients du réseau.

Manifest (data/updates.json) à mettre à jour manuellement côté serveur
lors de chaque release :
  {
    "version": "1.9.0",
    "url": "http://192.168.1.50:8765/static/EMS_v1.9.0.zip",
    "notes": "Nouveautés...",
    "required": false
  }
"""
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/updates", tags=["updates"])

_MANIFEST = Path(__file__).parent.parent / "data" / "updates.json"


class UpdateManifest(BaseModel):
    version: str
    url: str = ""
    notes: str = ""
    required: bool = False


@router.get("/latest", response_model=UpdateManifest, summary="Dernière version disponible")
def get_latest():
    if not _MANIFEST.is_file():
        raise HTTPException(status_code=404, detail="Manifest de mise à jour introuvable.")
    try:
        return UpdateManifest(**json.loads(_MANIFEST.read_text(encoding="utf-8")))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/latest", response_model=UpdateManifest, summary="Mettre à jour le manifest (admin)")
def set_latest(payload: UpdateManifest):
    """Met à jour le manifest côté serveur. Protéger cet endpoint si AUTH_ENABLED."""
    _MANIFEST.write_text(
        json.dumps(payload.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload
