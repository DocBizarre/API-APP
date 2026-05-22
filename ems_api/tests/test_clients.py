"""Tests d'intégration de l'API Clients."""

def test_create_client(client):
    r = client.post("/clients", json={"nom": "OCEA", "email": "o@x.fr"})
    assert r.status_code == 201
    assert r.json()["nom"] == "OCEA"


def test_create_client_upsert(client):
    r1 = client.post("/clients", json={"nom": "OCEA", "contact": "M.X"})
    r2 = client.post("/clients", json={"nom": "OCEA", "contact": "M.Y"})
    assert r1.json()["id"] == r2.json()["id"]
    assert r2.json()["contact"] == "M.Y"


def test_list_and_search(client):
    client.post("/clients", json={"nom": "OCEA"})
    client.post("/clients", json={"nom": "NAVAL GROUP"})
    assert len(client.get("/clients").json()) == 2
    assert len(client.get("/clients?search=oce").json()) == 1


def test_update_client(client, client_id):
    r = client.put(f"/clients/{client_id}", json={"email": "new@ocea.fr"})
    assert r.status_code == 200
    assert r.json()["email"] == "new@ocea.fr"


def test_delete_client(client, client_id):
    assert client.delete(f"/clients/{client_id}").status_code == 204
    assert client.get(f"/clients/{client_id}").status_code == 404


def test_get_inexistant_404(client):
    assert client.get("/clients/inexistant").status_code == 404
