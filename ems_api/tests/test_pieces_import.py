"""Import en masse du catalogue des références produits (dont simulation)."""


def _bulk(client, pieces, **kw):
    r = client.post("/pieces/bulk", json={"pieces": pieces, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def test_dry_run_n_ecrit_rien(client):
    res = _bulk(client, [{"reference": "REF-1"}, {"reference": "REF-2"}], dry_run=True)
    assert res["importees"] == 2
    assert client.get("/pieces/count").json()["total"] == 0


def test_skip_doublons_complete_sans_ecraser(client):
    _bulk(client, [{"reference": "REF-1", "libelle": "Filtre", "prix_achat": 0}])
    res = _bulk(client, [{"reference": "REF-1", "libelle": "AUTRE", "prix_achat": 12.5}],
                skip_doublons=True)
    assert res["ignorees"] == 1 and res["completees"] == 1
    p = client.get("/pieces?search=REF-1").json()[0]
    assert p["libelle"] == "Filtre" and p["prix_achat"] == 12.5
