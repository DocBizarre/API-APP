"""Fixtures partagées entre tous les tests."""
import sys
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="function")
def client(tmp_path, monkeypatch):
    """Client de test FastAPI avec base SQLite jetable."""
    # Nettoyer les modules ems_api avant rechargement (isolement)
    for mod in list(sys.modules):
        if mod.startswith("ems_api"):
            del sys.modules[mod]
    monkeypatch.setenv("EMS_DATA_DIR", str(tmp_path))
    from ems_api import main as api_main
    return TestClient(api_main.app)


@pytest.fixture
def client_id(client):
    """Crée un client de test et retourne son ID."""
    return client.post("/clients", json={"nom": "TEST CLIENT"}).json()["id"]


@pytest.fixture
def moteur_id(client, client_id):
    """Crée un moteur de test et retourne son ID."""
    return client.post("/moteurs", json={
        "client_id": client_id,
        "num_serie": "TEST-001",
        "marque": "BAUDOUIN",
    }).json()["id"]
