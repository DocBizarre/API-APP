"""Tests de la base fournisseurs (achats)."""


def _bc(client, **kw):
    body = {"fournisseur_nom": "SCANIA FRANCE", "fournisseur_ville": "ANGERS",
            "fournisseur_contact": "Nolwenn", "lignes": []}
    body.update(kw)
    r = client.post("/bons-commande", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_bon_commande_alimente_la_base(client):
    _bc(client)
    fs = client.get("/fournisseurs").json()
    assert len(fs) == 1
    f = fs[0]
    assert f["nom"] == "SCANIA FRANCE" and f["ville"] == "ANGERS"
    assert f["contact"] == "Nolwenn" and f["usage_count"] == 1 and f["id"]


def test_upsert_insensible_casse_et_complete_les_vides(client):
    _bc(client, fournisseur_ville="")
    _bc(client, fournisseur_nom="  scania france ", fournisseur_ville="ANGERS",
        fournisseur_contact="Autre")
    fs = client.get("/fournisseurs").json()
    assert len(fs) == 1
    assert fs[0]["usage_count"] == 2
    assert fs[0]["ville"] == "ANGERS"          # champ vide complété
    assert fs[0]["contact"] == "Nolwenn"       # champ existant conservé


def test_crud(client):
    r = client.post("/fournisseurs", json={"nom": "BAUDOUIN", "ville": "CASSIS"})
    assert r.status_code == 201
    fid = r.json()["id"]
    # POST sur un nom existant (casse différente) = mise à jour, pas de doublon
    client.post("/fournisseurs", json={"nom": "baudouin", "email": "x@b.com"})
    assert len(client.get("/fournisseurs").json()) == 1
    r = client.put(f"/fournisseurs/{fid}", json={"pays": "France"})
    assert r.json()["pays"] == "France" and r.json()["email"] == "x@b.com"
    assert client.get(f"/fournisseurs/{fid}").json()["ville"] == "CASSIS"
    assert client.get("/fournisseurs?search=cass").json()[0]["id"] == fid
    assert client.delete(f"/fournisseurs/{fid}").status_code == 204
    assert client.get(f"/fournisseurs/{fid}").status_code == 404


def test_renommage_en_doublon_refuse(client):
    a = client.post("/fournisseurs", json={"nom": "ZF"}).json()["id"]
    client.post("/fournisseurs", json={"nom": "PERKINS"})
    assert client.put(f"/fournisseurs/{a}", json={"nom": "perkins"}).status_code == 409
    assert client.put(f"/fournisseurs/{a}", json={"nom": ""}).status_code == 422
