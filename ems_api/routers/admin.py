"""
Router admin - Endpoints d'administration.

Pour l'instant : export de la base SQLite pour l'app BI.
Le BI a besoin de la DB complete pour faire ses analyses cote navigateur (SQL.js).
"""
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..database import engine

router = APIRouter(prefix="/admin", tags=["admin"])


def _get_db_path() -> Path:
    """Extrait le chemin du fichier SQLite depuis l'URL SQLAlchemy."""
    url = str(engine.url)
    # Forme typique : sqlite:///C:/path/to/ems.db ou sqlite:///./data/ems.db
    if url.startswith("sqlite:///"):
        return Path(url.replace("sqlite:///", "", 1))
    if url.startswith("sqlite://"):
        return Path(url.replace("sqlite://", "", 1))
    raise RuntimeError(f"URL non SQLite : {url}")


@router.get("/export-db",
            summary="Telecharge la base SQLite complete",
            response_class=FileResponse)
def export_db():
    """
    Renvoie le fichier ems.db en binaire pour usage par l'app BI.
    A utiliser en lecture seule cote client.
    """
    try:
        db_file = _get_db_path()
    except RuntimeError as e:
        raise HTTPException(500, str(e))

    if not db_file.is_file():
        raise HTTPException(404, f"Base introuvable : {db_file}")
    return FileResponse(
        path=str(db_file),
        media_type="application/octet-stream",
        filename="ems.db",
        headers={"Cache-Control": "no-store"})
