"""
Endpoint de conversion d'accusés de réception de commande EMS.

POST /pdf/accuse-reception
  → accepte un PDF ERP en upload, retourne un PDF remis en page EMS.

Les lourdes dépendances (pdfplumber, WeasyPrint, PIL, pypdf) restent sur le
serveur. Les clients .exe n'ont plus besoin de les embarquer.
"""
import sys
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response

router = APIRouter(prefix="/pdf", tags=["pdf"])

# Assurer que la racine du projet est dans sys.path pour importer convertisseurpdf
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _process_bytes(pdf_bytes: bytes, include_cgv: bool) -> bytes:
    """Traitement synchrone exécuté dans le threadpool uvicorn."""
    import importlib
    # Rechargement automatique si le fichier source a été modifié depuis le dernier import.
    _mod_file = _ROOT / "convertisseurpdf.py"
    _mod_name = "convertisseurpdf"
    current_mtime = _mod_file.stat().st_mtime if _mod_file.exists() else 0
    if _mod_name in sys.modules:
        mod = sys.modules[_mod_name]
        cached_mtime = getattr(mod, "_file_mtime_", 0)
        if current_mtime != cached_mtime:
            # Supprimer du cache pour forcer un import propre
            del sys.modules[_mod_name]
    try:
        from convertisseurpdf import (
            parse_commande, extract_logo_datauri, build_html, _render_to_bytes,
        )
        # Stocker le mtime après import
        if _mod_name in sys.modules:
            sys.modules[_mod_name]._file_mtime_ = current_mtime
    except ImportError as exc:
        raise RuntimeError(f"Module convertisseurpdf non disponible : {exc}")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        data = parse_commande(tmp_path)
        logo = extract_logo_datauri(tmp_path)
        html_str = build_html(data, logo)
        return _render_to_bytes(data, html_str, source_pdf=tmp_path, include_cgv=include_cgv)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@router.post(
    "/accuse-reception",
    summary="Convertit un accusé de réception ERP en PDF mis en page EMS",
    response_class=Response,
)
async def convertir_accuse_reception(
    file: UploadFile = File(..., description="PDF accusé de réception ERP"),
    include_cgv: bool = Query(True, description="Inclure les CGV en dernière page"),
):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "Le fichier doit être un PDF (.pdf)")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(400, "Fichier vide")

    try:
        result = await run_in_threadpool(_process_bytes, pdf_bytes, include_cgv)
    except RuntimeError as exc:
        raise HTTPException(500, str(exc))
    except Exception as exc:
        raise HTTPException(500, f"Erreur de conversion : {exc}")

    stem = Path(file.filename or "accuse").stem
    return Response(
        content=result,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{stem}_accuse_EMS.pdf"',
            "Cache-Control": "no-store",
        },
    )
