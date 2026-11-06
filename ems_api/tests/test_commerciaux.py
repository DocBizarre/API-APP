"""Commercial EMS des affaires + table de précomplétion /commerciaux."""


def test_affaire_avec_commercial_alimente_la_table(client):
    r = client.post("/affaires", json={"nom_projet": "Remotorisation", "charge_affaire": "Paul",
                                       "commercial": "Jean Dupont",
                                       "commercial_email": "j.dupont@ems.fr",
                                       "commercial_tel": "+33 6 12 34 56 78"})
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["commercial"] == "Jean Dupont" and a["commercial_email"] == "j.dupont@ems.fr"

    cs = client.get("/commerciaux").json()
    assert len(cs) == 1
    assert cs[0]["nom"] == "Jean Dupont" and cs[0]["telephone"] == "+33 6 12 34 56 78"
    assert cs[0]["nb_affaires"] == 1

    # Recherche d'affaires par commercial
    r = client.get("/affaires", params={"search": "dupont", "limit": 10})
    assert r.json()["total"] == 1

    # Mise à jour : même commercial (casse différente) → pas de doublon, champs vides complétés
    client.put(f"/affaires/{a['id']}", json={"commercial": "jean dupont"})
    cs = client.get("/commerciaux").json()
    assert len(cs) == 1 and cs[0]["usage_count"] == 2


def test_upsert_ne_remplace_pas_les_champs_renseignes(client):
    client.post("/commerciaux", json={"nom": "Marie", "email": "marie@ems.fr"})
    client.post("/affaires", json={"nom_projet": "X", "commercial": "MARIE",
                                   "commercial_email": "autre@ems.fr", "commercial_tel": "0600000000"})
    c = client.get("/commerciaux").json()[0]
    assert c["email"] == "marie@ems.fr" and c["telephone"] == "0600000000"


def test_crud(client):
    r = client.post("/commerciaux", json={"nom": "  Luc  ", "email": "luc@ems.fr"})
    assert r.status_code == 201
    cid = r.json()["id"]
    assert r.json()["nom"] == "Luc"
    assert client.post("/commerciaux", json={"nom": ""}).status_code == 422

    client.post("/commerciaux", json={"nom": "Anne"})
    assert client.put(f"/commerciaux/{cid}", json={"nom": "anne"}).status_code == 409
    r = client.put(f"/commerciaux/{cid}", json={"telephone": "0611111111"})
    assert r.json()["telephone"] == "0611111111" and r.json()["email"] == "luc@ems.fr"

    assert client.delete(f"/commerciaux/{cid}").status_code == 204
    assert client.get(f"/commerciaux/{cid}").status_code == 404
    assert [c["nom"] for c in client.get("/commerciaux").json()] == ["Anne"]
