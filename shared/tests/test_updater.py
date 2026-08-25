"""Tests du module de mise à jour automatique (shared/updater.py)."""
import io
import subprocess
import threading
import zipfile
from pathlib import Path

import pytest

from shared import updater


# ─── Comparaison de versions ──────────────────────────────────────────────────

@pytest.mark.parametrize("a,b,expected", [
    ("1.9.1", "1.9.0", True),
    ("1.10.0", "1.9.9", True),   # comparaison numérique, pas lexicographique
    ("2.0.0", "1.9.9", True),
    ("1.9.0", "1.9.0", False),
    ("1.9.0", "1.9.1", False),
])
def test_ver_comparison(a, b, expected):
    assert (updater._ver(a) > updater._ver(b)) is expected


def test_ver_invalid_string_is_lowest():
    assert updater._ver("pas-une-version") == (0,)
    assert updater._ver("1.2.x") == (0,)


# ─── check_for_update ──────────────────────────────────────────────────────────

class _FakeResponse:
    def __init__(self, ok=True, payload=None):
        self.ok = ok
        self._payload = payload or {}

    def json(self):
        return self._payload


def test_check_for_update_returns_info_when_newer(monkeypatch):
    monkeypatch.setattr(updater, "_HAS_REQUESTS", True)
    fake = _FakeResponse(ok=True, payload={"version": "1.9.5", "url": "http://x/y.zip"})
    monkeypatch.setattr(updater._requests, "get", lambda url, timeout: fake)

    info = updater.check_for_update("http://server:8765", "1.9.0")
    assert info == {"version": "1.9.5", "url": "http://x/y.zip"}


def test_check_for_update_returns_none_when_same_or_older(monkeypatch):
    monkeypatch.setattr(updater, "_HAS_REQUESTS", True)
    fake = _FakeResponse(ok=True, payload={"version": "1.9.0"})
    monkeypatch.setattr(updater._requests, "get", lambda url, timeout: fake)

    assert updater.check_for_update("http://server:8765", "1.9.0") is None


def test_check_for_update_returns_none_on_bad_response(monkeypatch):
    monkeypatch.setattr(updater, "_HAS_REQUESTS", True)
    monkeypatch.setattr(updater._requests, "get", lambda url, timeout: _FakeResponse(ok=False))

    assert updater.check_for_update("http://server:8765", "1.9.0") is None


def test_check_for_update_returns_none_on_exception(monkeypatch):
    monkeypatch.setattr(updater, "_HAS_REQUESTS", True)

    def _raise(*a, **k):
        raise ConnectionError("serveur injoignable")

    monkeypatch.setattr(updater._requests, "get", _raise)
    assert updater.check_for_update("http://server:8765", "1.9.0") is None


def test_check_for_update_returns_none_without_requests(monkeypatch):
    monkeypatch.setattr(updater, "_HAS_REQUESTS", False)
    assert updater.check_for_update("http://server:8765", "1.9.0") is None


def test_check_for_update_hits_expected_url(monkeypatch):
    monkeypatch.setattr(updater, "_HAS_REQUESTS", True)
    seen = {}

    def _get(url, timeout):
        seen["url"] = url
        seen["timeout"] = timeout
        return _FakeResponse(ok=True, payload={"version": "0.0.0"})

    monkeypatch.setattr(updater._requests, "get", _get)
    updater.check_for_update("http://server:8765/", "1.9.0")
    assert seen["url"] == "http://server:8765/updates/latest"
    assert seen["timeout"] == 5


# ─── _worker (téléchargement + extraction + script) ────────────────────────────

def _make_zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("hello.txt", "world")
    return buf.getvalue()


class _FakeStreamResponse:
    def __init__(self, data: bytes):
        self._data = data
        self.headers = {"content-length": str(len(data))}

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        for i in range(0, len(self._data), chunk_size):
            yield self._data[i:i + chunk_size]


def test_worker_downloads_extracts_and_writes_batch(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "_HAS_REQUESTS", True)
    monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(tmp_path))

    zip_bytes = _make_zip_bytes()
    monkeypatch.setattr(
        updater._requests, "get",
        lambda url, stream, timeout: _FakeStreamResponse(zip_bytes))

    install_dir = tmp_path / "install"
    install_dir.mkdir()

    progress_msgs = []
    done = {}
    errors = []

    updater._worker(
        {"url": "http://x/EMS_v1.9.5.zip", "version": "1.9.5"},
        install_dir,
        on_progress=lambda msg, pct: progress_msgs.append((msg, pct)),
        on_done=lambda batch_path: done.setdefault("path", batch_path),
        on_error=lambda msg: errors.append(msg),
    )

    assert not errors
    assert "path" in done
    batch_path = Path(done["path"])
    assert batch_path.is_file()

    script = batch_path.read_text(encoding="utf-8")
    assert str(install_dir) in script
    assert "EMS_Launcher.exe" in script
    assert progress_msgs

    extracted = tmp_path / "ems_update_1.9.5" / "hello.txt"
    assert extracted.is_file()
    assert extracted.read_text(encoding="utf-8") == "world"

    # Le zip temporaire est nettoyé après extraction
    assert not (tmp_path / "ems_update_1.9.5.zip").exists()


def test_worker_missing_url_calls_on_error(tmp_path):
    errors = []
    updater._worker(
        {"version": "1.9.5"},  # pas d'URL configurée dans le manifest
        tmp_path,
        on_progress=None, on_done=None,
        on_error=lambda msg: errors.append(msg),
    )
    assert len(errors) == 1
    assert "URL" in errors[0]


def test_worker_without_requests_calls_on_error(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "_HAS_REQUESTS", False)
    errors = []
    updater._worker(
        {"url": "http://x/y.zip", "version": "1.9.5"},
        tmp_path,
        on_progress=None, on_done=None,
        on_error=lambda msg: errors.append(msg),
    )
    assert len(errors) == 1
    assert "requests" in errors[0]


def test_worker_download_exception_calls_on_error(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "_HAS_REQUESTS", True)
    monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(tmp_path))

    def _raise(*a, **k):
        raise TimeoutError("serveur ne répond pas")

    monkeypatch.setattr(updater._requests, "get", _raise)

    errors = []
    updater._worker(
        {"url": "http://x/y.zip", "version": "1.9.5"},
        tmp_path / "install",
        on_progress=None, on_done=None,
        on_error=lambda msg: errors.append(msg),
    )
    assert len(errors) == 1
    assert "serveur ne répond pas" in errors[0]


def test_download_and_apply_runs_in_background_thread(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "_HAS_REQUESTS", True)
    monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(tmp_path))
    zip_bytes = _make_zip_bytes()
    monkeypatch.setattr(
        updater._requests, "get",
        lambda url, stream, timeout: _FakeStreamResponse(zip_bytes))

    done_event = threading.Event()
    result = {}

    def _on_done(batch_path):
        result["path"] = batch_path
        done_event.set()

    updater.download_and_apply(
        {"url": "http://x/EMS_v2.0.0.zip", "version": "2.0.0"},
        tmp_path / "install",
        on_done=_on_done,
    )

    assert done_event.wait(timeout=5), "on_done n'a pas été appelé à temps"
    assert Path(result["path"]).is_file()


# ─── launch_batch_and_quit ──────────────────────────────────────────────────────

def test_launch_batch_and_quit_spawns_process_and_quits(monkeypatch):
    calls = {}

    def _fake_popen(args, creationflags=None):
        calls["args"] = args
        calls["creationflags"] = creationflags
        return object()

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)

    quit_called = []
    updater.launch_batch_and_quit(
        "C:\\temp\\ems_apply_update.bat", lambda: quit_called.append(True))

    assert calls["args"] == ["cmd.exe", "/c", "C:\\temp\\ems_apply_update.bat"]
    assert quit_called == [True]
