"""Tests de l'endpoint /updates (manifest de mise à jour)."""
import json
import sys


def _updates_module():
    """Le module ems_api.routers.updates rechargé par la fixture `client`."""
    return sys.modules["ems_api.routers.updates"]


def test_get_latest_manifest(client, tmp_path, monkeypatch):
    manifest = tmp_path / "updates.json"
    manifest.write_text(json.dumps({
        "version": "2.0.0",
        "url": "http://192.168.1.10:8765/static/EMS_v2.0.0.zip",
        "notes": "Correctifs divers.",
        "required": True,
    }), encoding="utf-8")
    monkeypatch.setattr(_updates_module(), "_MANIFEST", manifest)

    r = client.get("/updates/latest")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "2.0.0"
    assert body["required"] is True


def test_get_latest_manifest_missing_returns_404(client, tmp_path, monkeypatch):
    monkeypatch.setattr(_updates_module(), "_MANIFEST", tmp_path / "absent.json")

    r = client.get("/updates/latest")
    assert r.status_code == 404


def test_get_latest_manifest_corrupt_returns_500(client, tmp_path, monkeypatch):
    manifest = tmp_path / "updates.json"
    manifest.write_text("{ceci n'est pas du json", encoding="utf-8")
    monkeypatch.setattr(_updates_module(), "_MANIFEST", manifest)

    r = client.get("/updates/latest")
    assert r.status_code == 500


def test_put_latest_manifest_writes_file(client, tmp_path, monkeypatch):
    manifest = tmp_path / "updates.json"
    monkeypatch.setattr(_updates_module(), "_MANIFEST", manifest)

    payload = {
        "version": "2.1.0",
        "url": "http://192.168.1.10:8765/static/EMS_v2.1.0.zip",
        "notes": "Nouvelle version.",
        "required": False,
    }
    r = client.put("/updates/latest", json=payload)
    assert r.status_code == 200
    assert r.json()["version"] == "2.1.0"

    saved = json.loads(manifest.read_text(encoding="utf-8"))
    assert saved == payload


def test_put_latest_manifest_applies_defaults(client, tmp_path, monkeypatch):
    manifest = tmp_path / "updates.json"
    monkeypatch.setattr(_updates_module(), "_MANIFEST", manifest)

    r = client.put("/updates/latest", json={"version": "2.2.0"})
    assert r.status_code == 200
    body = r.json()
    assert body["url"] == ""
    assert body["notes"] == ""
    assert body["required"] is False


def test_put_then_get_roundtrip(client, tmp_path, monkeypatch):
    manifest = tmp_path / "updates.json"
    monkeypatch.setattr(_updates_module(), "_MANIFEST", manifest)

    client.put("/updates/latest", json={"version": "3.0.0", "required": True})
    r = client.get("/updates/latest")
    assert r.status_code == 200
    assert r.json()["version"] == "3.0.0"
    assert r.json()["required"] is True
