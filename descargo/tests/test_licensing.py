import json

import pytest
from Cryptodome.PublicKey import ECC

from descargo.core import licensing
from descargo.core.licensing import (FREE_DAILY_LIMIT, LicenseError, LicenseManager,
                                     create_license, machine_code, verify_license)


@pytest.fixture
def keypair(monkeypatch):
    """Llave de prueba: la app de pruebas confía en ella en lugar de la real."""
    key = ECC.generate(curve="ed25519")
    monkeypatch.setattr(licensing, "PUBLIC_KEY_PEM", key.public_key().export_key(format="PEM"))
    return key.export_key(format="PEM")


def test_machine_code_format_and_stable():
    code = machine_code()
    assert len(code) == 19 and code.count("-") == 3
    assert machine_code() == code


def test_valid_license_roundtrip(keypair):
    key = create_license(keypair, "María Quispe", machine_code())
    lic = verify_license("  " + key[:30] + "\n" + key[30:] + " ")  # tolera saltos al pegar
    assert lic.name == "María Quispe" and lic.expires is None and not lic.expired


def test_license_for_other_machine_rejected(keypair):
    key = create_license(keypair, "X", "AAAA-BBBB-CCCC-DDDD")
    with pytest.raises(LicenseError, match="otro equipo"):
        verify_license(key)


def test_expired_and_tampered_rejected(keypair):
    with pytest.raises(LicenseError, match="venció"):
        verify_license(create_license(keypair, "X", machine_code(), "2020-01-01"))
    good = create_license(keypair, "X", machine_code())
    body, sig = good[len("DGO1-"):].split(".")
    data = json.loads(licensing._b64d(body))
    data["n"] = "Pirata"
    forged = "DGO1-" + licensing._b64e(json.dumps(data).encode()) + "." + sig
    with pytest.raises(LicenseError, match="firma"):
        verify_license(forged)
    with pytest.raises(LicenseError):
        verify_license("cualquier cosa")


def test_license_signed_with_other_key_rejected(keypair):
    other = ECC.generate(curve="ed25519").export_key(format="PEM")
    with pytest.raises(LicenseError, match="firma"):
        verify_license(create_license(other, "X", machine_code()))


def test_real_public_key_is_valid():
    ECC.import_key(licensing.PUBLIC_KEY_PEM)  # la llave pública incluida carga bien


def test_daily_limit_and_license(tmp_path, keypair):
    lm = LicenseManager(tmp_path)
    assert lm.remaining_today() == FREE_DAILY_LIMIT
    for _ in range(3):
        lm.record_download()
    assert lm.remaining_today() == FREE_DAILY_LIMIT - 3
    # manipular el contador lo agota (no lo reinicia)
    data = json.loads((tmp_path / "uso.json").read_text())
    data["c"] = 0
    (tmp_path / "uso.json").write_text(json.dumps(data))
    assert lm.remaining_today() == 0
    lm.activate(create_license(keypair, "Cliente", machine_code()))
    assert lm.licensed and lm.remaining_today() is None
    assert LicenseManager(tmp_path).licensed  # persiste al reabrir
    lm.deactivate()
    assert not LicenseManager(tmp_path).licensed


def test_private_key_never_in_repo():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    hits = [p for p in root.rglob("*") if p.is_file() and ".git" not in p.parts
            and p.suffix in (".key", ".pem", ".py", ".txt", ".md")
            and ("-----BEGIN " + "PRIVATE KEY-----") in p.read_text(errors="ignore")]
    assert hits == [], hits
