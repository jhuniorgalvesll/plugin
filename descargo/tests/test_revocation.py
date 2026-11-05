import functools
import http.server
import threading

import pytest
from Cryptodome.PublicKey import ECC

from descargo.core import licensing, revocation
from descargo.core.licensing import LicenseManager, create_license, machine_code


@pytest.fixture
def keypair(monkeypatch):
    key = ECC.generate(curve="ed25519")
    monkeypatch.setattr(licensing, "PUBLIC_KEY_PEM", key.public_key().export_key(format="PEM"))
    return key.export_key(format="PEM")


def test_license_has_unique_id(keypair):
    k1 = create_license(keypair, "A", machine_code())
    k2 = create_license(keypair, "A", machine_code())
    from descargo.core.licensing import verify_license
    assert verify_license(k1).lid and verify_license(k1).lid != verify_license(k2).lid


def test_revocation_file_signed_and_verified(keypair):
    text = revocation.build_revocation_file(keypair, ["abc", "def", "abc", " "])
    assert revocation.parse_revocation_file(text) == {"abc", "def"}
    # firma inválida -> no revoca nada
    tampered = text.replace("abc", "xyz")
    assert revocation.parse_revocation_file(tampered) == set()
    # firmada con otra llave -> rechazada
    other = ECC.generate(curve="ed25519").export_key(format="PEM")
    assert revocation.parse_revocation_file(revocation.build_revocation_file(other, ["abc"])) == set()


def test_manager_applies_revocation(tmp_path, keypair):
    lm = LicenseManager(tmp_path)
    key = create_license(keypair, "Cliente", machine_code())
    lm.activate(key)
    assert lm.licensed and not lm.is_revoked
    lid = lm.license.lid
    # sin conexión (None): no cambia nada
    assert not lm.apply_revoked_ids(None)
    assert lm.licensed
    # aparece en la lista -> anulada, y persiste al reabrir
    assert lm.apply_revoked_ids({lid})
    assert lm.is_revoked and not lm.licensed
    assert LicenseManager(tmp_path).is_revoked
    # se quita de la lista -> vuelve a estar activa
    assert not lm.apply_revoked_ids(set())
    assert lm.licensed and not lm.is_revoked


def test_author_never_revoked(tmp_path, keypair):
    lm = LicenseManager(tmp_path)
    (tmp_path / licensing.PRIVATE_KEY_FILENAME).write_text(keypair)
    lm = LicenseManager(tmp_path)
    assert lm.is_author and lm.licensed and not lm.is_revoked


def test_fetch_revoked_ids_over_http(tmp_path, keypair, monkeypatch):
    root = tmp_path / "www"
    root.mkdir()
    (root / "revocaciones.json").write_text(revocation.build_revocation_file(keypair, ["r1", "r2"]))

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(root)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    monkeypatch.setattr(revocation, "REVOCATION_URL",
                        f"http://127.0.0.1:{httpd.server_address[1]}/revocaciones.json")
    try:
        assert revocation.fetch_revoked_ids() == {"r1", "r2"}
    finally:
        httpd.shutdown()


def test_fetch_missing_list_is_empty_not_none(tmp_path, keypair, monkeypatch):
    root = tmp_path / "www"
    root.mkdir()

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(root)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    monkeypatch.setattr(revocation, "REVOCATION_URL",
                        f"http://127.0.0.1:{httpd.server_address[1]}/no-existe.json")
    try:
        assert revocation.fetch_revoked_ids() == set()   # 404 -> nada anulado (no None)
    finally:
        httpd.shutdown()
