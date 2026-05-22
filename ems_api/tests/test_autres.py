"""Tests Garanties, Améliorations, Techniciens."""


# ─── GARANTIES ───────────────────────────────────────────────────────────────
def test_create_garantie(client, client_id, moteur_id):
    r = client.post("/garanties", json={
        "num_constructeur": "BD-001",
        "client_id": client_id, "moteur_id": moteur_id,
        "attribution": "BAUDOUIN", "statut": "Suivi EMS",
    })
    assert r.status_code == 201
    assert r.json()["num_ems"].startswith("GAR-")
    assert r.json()["client_nom"] == "TEST CLIENT"
    assert r.json()["moteur_serie"] == "TEST-001"


def test_garanties_by_moteur(client, client_id, moteur_id):
    client.post("/garanties", json={"client_id": client_id,
                                      "moteur_id": moteur_id})
    client.post("/garanties", json={"client_id": client_id,
                                      "moteur_id": moteur_id})
    assert len(client.get(f"/garanties/by-moteur/{moteur_id}").json()) == 2


def test_attributions(client, client_id):
    client.post("/moteurs", json={"client_id": client_id,
                                    "num_serie": "X1", "marque": "BAUDOUIN"})
    client.post("/moteurs", json={"client_id": client_id,
                                    "num_serie": "X2", "marque": "SCANIA"})
    attribs = client.get("/garanties/attributions").json()
    assert "BAUDOUIN" in attribs
    assert "SCANIA" in attribs
    assert "Interne EMS" in attribs
    assert "Mixte" in attribs


def test_filter_garantie_par_statut(client, client_id):
    client.post("/garanties", json={"client_id": client_id, "statut": "Suivi EMS"})
    client.post("/garanties", json={"client_id": client_id, "statut": "Clôturée"})
    r = client.get("/garanties?statut=Clôturée")
    assert len(r.json()) == 1


# ─── AMÉLIORATIONS ──────────────────────────────────────────────────────────
def test_create_amelioration(client, client_id):
    r = client.post("/ameliorations", json={
        "titre": "Export Excel", "client_id": client_id,
        "priorite": "Haute", "statut": "Nouveau"
    })
    assert r.status_code == 201
    assert r.json()["num_ticket"].startswith("AMELIO-")


def test_stats_ameliorations(client, client_id):
    client.post("/ameliorations", json={"client_id": client_id, "statut": "Nouveau"})
    client.post("/ameliorations", json={"client_id": client_id, "statut": "Nouveau"})
    client.post("/ameliorations", json={"client_id": client_id, "statut": "Résolu"})
    s = client.get("/ameliorations/stats").json()
    assert s["Total"] == 3
    assert s["Nouveau"] == 2
    assert s["Résolu"] == 1


def test_filter_amelio_priorite(client, client_id):
    client.post("/ameliorations", json={"client_id": client_id, "priorite": "Haute"})
    client.post("/ameliorations", json={"client_id": client_id, "priorite": "Basse"})
    assert len(client.get("/ameliorations?priorite=Haute").json()) == 1


# ─── TECHNICIENS ────────────────────────────────────────────────────────────
def test_create_technicien(client):
    r = client.post("/techniciens", json={"nom": "Jean MARTIN",
                                            "email": "jm@x.fr"})
    assert r.status_code == 201
    assert r.json()["nom"] == "Jean MARTIN"


def test_upsert_technicien_par_nom(client):
    r1 = client.post("/techniciens", json={"nom": "Jean", "email": "old@x.fr"})
    r2 = client.post("/techniciens", json={"nom": "Jean", "email": "new@x.fr"})
    assert r1.json()["id"] == r2.json()["id"]
    assert r2.json()["email"] == "new@x.fr"


def test_delete_technicien(client):
    r = client.post("/techniciens", json={"nom": "Jean"}).json()
    assert client.delete(f"/techniciens/{r['id']}").status_code == 204
    assert client.get(f"/techniciens/{r['id']}").status_code == 404
