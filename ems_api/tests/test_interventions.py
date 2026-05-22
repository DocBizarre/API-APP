"""Tests d'intégration des Interventions (+ signatures)."""


def test_create_intervention_genere_num_bon(client, client_id, moteur_id):
    r = client.post("/interventions", json={
        "client_id": client_id, "moteur_id": moteur_id,
        "type_intervention": "Dépannage",
        "urgence": "Normale", "technicien": "Jean"
    })
    assert r.status_code == 201
    num = r.json()["num_bon"]
    assert num.startswith("BON-") and num.endswith("0001")


def test_numerotation_incrementale(client, client_id, moteur_id):
    n1 = client.post("/interventions", json={"client_id": client_id,
                                              "moteur_id": moteur_id}).json()
    n2 = client.post("/interventions", json={"client_id": client_id,
                                              "moteur_id": moteur_id}).json()
    assert int(n1["num_bon"].split("-")[-1]) + 1 == int(n2["num_bon"].split("-")[-1])


def test_signature_client(client, client_id, moteur_id):
    inv = client.post("/interventions", json={"client_id": client_id,
                                                "moteur_id": moteur_id,
                                                "technicien": "Jean"}).json()
    r = client.post(f"/interventions/{inv['id']}/signature", json={
        "signature_b64": "iVBORw0KGgo=",
        "signature_nom": "M.Client", "role": "client"})
    assert r.json()["signature_nom"] == "M.Client"
    assert r.json()["signature_date"]   # horodatage non vide
    assert not r.json()["signature_tech_nom"]


def test_signature_technicien(client, client_id, moteur_id):
    inv = client.post("/interventions", json={"client_id": client_id,
                                                "moteur_id": moteur_id}).json()
    r = client.post(f"/interventions/{inv['id']}/signature", json={
        "signature_b64": "iVBORw0KGgo=",
        "signature_nom": "Jean MARTIN", "role": "technicien"})
    assert r.json()["signature_tech_nom"] == "Jean MARTIN"
    assert r.json()["signature_tech_date"]
    assert not r.json()["signature_nom"]


def test_urgentes(client, client_id, moteur_id):
    client.post("/interventions", json={"client_id": client_id,
                                          "urgence": "Normale", "statut": "En cours"})
    client.post("/interventions", json={"client_id": client_id,
                                          "urgence": "Urgente", "statut": "En cours"})
    client.post("/interventions", json={"client_id": client_id,
                                          "urgence": "Critique", "statut": "Clos"})
    r = client.get("/interventions/urgentes")
    # Urgente (en cours) seulement — Critique est Clos
    assert len(r.json()) == 1
    assert r.json()[0]["urgence"] == "Urgente"


def test_filter_par_statut(client, client_id):
    client.post("/interventions", json={"client_id": client_id, "statut": "En cours"})
    client.post("/interventions", json={"client_id": client_id, "statut": "Clos"})
    assert len(client.get("/interventions?statut=Clos").json()) == 1
    assert len(client.get("/interventions?statut=Tous").json()) == 2


def test_by_moteur(client, client_id, moteur_id):
    client.post("/interventions", json={"client_id": client_id, "moteur_id": moteur_id})
    client.post("/interventions", json={"client_id": client_id})  # sans moteur
    r = client.get(f"/interventions/by-moteur/{moteur_id}")
    assert len(r.json()) == 1


def test_notifie(client, client_id):
    inv = client.post("/interventions", json={"client_id": client_id}).json()
    assert inv["client_notifie"] == 0
    r = client.post(f"/interventions/{inv['id']}/notifie/client", json={})
    assert r.json()["client_notifie"] == 1


def test_update_statut(client, client_id):
    inv = client.post("/interventions", json={"client_id": client_id}).json()
    r = client.put(f"/interventions/{inv['id']}", json={"statut": "Facturé"})
    assert r.json()["statut"] == "Facturé"
