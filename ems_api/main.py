"""
═══════════════════════════════════════════════════════════════════════════════
  EMS – API  (serveur FastAPI)
═══════════════════════════════════════════════════════════════════════════════

Lancement :
    uvicorn ems_api.main:app --host 127.0.0.1 --port 8765 --reload

Documentation interactive auto-générée :
    http://127.0.0.1:8765/docs       (Swagger UI)
    http://127.0.0.1:8765/redoc      (ReDoc)

L'API expose des endpoints REST classiques :
    GET    /clients              liste
    GET    /clients/{id}         détail
    POST   /clients              création
    PUT    /clients/{id}         mise à jour
    DELETE /clients/{id}         suppression
    (idem pour /moteurs, /interventions, /garanties, /ameliorations, /techniciens)

═══════════════════════════════════════════════════════════════════════════════
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status, Header
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

from .config import settings
from .database import init_db
from .routers import (
    clients, moteurs, techniciens,
    interventions, garanties, ameliorations, documents,
    types_intervention, statuts_garantie, stats_config, pieces, sync,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialisation au démarrage."""
    init_db()
    # Lancer la sauvegarde quotidienne en arrière-plan
    try:
        from .backup import planifier_quotidien
        planifier_quotidien()
    except Exception as e:
        print(f"⚠ Sauvegarde auto non démarrée : {e}")
    yield


app = FastAPI(
    title="EMS API",
    description="API interne Emeraude Moteurs Systèmes — "
                "gestion des bons d'intervention, garanties, etc.",
    version="0.1.0",
    lifespan=lifespan,
)

# Initialisation immédiate (en plus du lifespan, pour TestClient/import direct)
init_db()

# ─── CORS ────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Authentification simple par clé d'API (optionnelle) ────────────────────
async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    if not settings.AUTH_ENABLED:
        return  # pas d'auth
    if x_api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé d'API invalide ou manquante (header X-API-Key)")


# ─── Routes ──────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "service": "EMS API",
        "version": app.version,
        "docs": "/docs",
        "auth": "enabled" if settings.AUTH_ENABLED else "disabled",
    }


@app.get("/health")
def health():
    """Endpoint de santé (pour monitoring)."""
    return {"status": "ok"}


# ─── Enregistrement des routers ─────────────────────────────────────────────
deps = [Depends(verify_api_key)] if settings.AUTH_ENABLED else []
app.include_router(clients.router, dependencies=deps)
app.include_router(moteurs.router, dependencies=deps)
app.include_router(techniciens.router, dependencies=deps)
app.include_router(interventions.router, dependencies=deps)
app.include_router(garanties.router, dependencies=deps)
app.include_router(ameliorations.router, dependencies=deps)
app.include_router(documents.router, dependencies=deps)
app.include_router(types_intervention.router, dependencies=deps)
app.include_router(statuts_garantie.router, dependencies=deps)
app.include_router(stats_config.router_stats, dependencies=deps)
app.include_router(stats_config.router_config, dependencies=deps)
app.include_router(pieces.router, dependencies=deps)
app.include_router(sync.router, dependencies=deps)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("ems_api.main:app",
                host=settings.HOST, port=settings.PORT, reload=True)
