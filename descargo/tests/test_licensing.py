import json

import pytest
from Cryptodome.PublicKey import ECC

from descargo.core import licensing
from descargo.core.licensing import (LicenseError, LicenseManager,
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


def test_license_persists_and_expired_is_kept(tmp_path, keypair):
    lm = LicenseManager(tmp_path)
    assert not lm.licensed and lm.expired_license is None
    lm.activate(create_license(keypair, "Cliente", machine_code()))
    assert lm.licensed and LicenseManager(tmp_path).licensed  # persiste al reabrir
    lm.deactivate()
    assert not LicenseManager(tmp_path).licensed
    # una licencia vencida se conserva para avisar, pero no da alta calidad
    from descargo.core import licensing as L
    key = create_license(keypair, "Cliente", machine_code(), "2020-01-01")
    (tmp_path / "licencia.txt").write_text(key)
    lm = LicenseManager(tmp_path)
    assert not lm.licensed and lm.expired_license.expires == "2020-01-01"


def test_private_key_never_in_repo():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    hits = [p for p in root.rglob("*") if p.is_file() and ".git" not in p.parts
            and p.suffix in (".key", ".pem", ".py", ".txt", ".md")
            and ("-----BEGIN " + "PRIVATE KEY-----") in p.read_text(errors="ignore")]
    assert hits == [], hits


def test_author_mode_requires_real_private_key(tmp_path, keypair):
    lm = LicenseManager(tmp_path)
    assert not lm.is_author
    # una llave cualquiera con el mismo nombre NO da modo autor
    fake = ECC.generate(curve="ed25519").export_key(format="PEM")
    (tmp_path / licensing.PRIVATE_KEY_FILENAME).write_text(fake)
    lm = LicenseManager(tmp_path)
    assert not lm.is_author and not lm.licensed
    # la llave real (la que corresponde a la pública de la app) sí
    (tmp_path / licensing.PRIVATE_KEY_FILENAME).write_text(keypair)
    lm = LicenseManager(tmp_path)
    assert lm.is_author and lm.licensed
    (tmp_path / licensing.PRIVATE_KEY_FILENAME).write_text("basura")
    assert not LicenseManager(tmp_path).is_author


def test_add_months_and_five_month_license(keypair):
    from datetime import date
    from descargo.core.licensing import add_months
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2026, 11, 5), 5) == date(2027, 4, 5)
    exp = add_months(date.today(), 5).isoformat()
    lic = verify_license(create_license(keypair, "Cinco meses", machine_code(), exp))
    assert lic.expires == exp and not lic.expired


def test_install_author_key_and_issued_log(tmp_path, keypair):
    lm = LicenseManager(tmp_path)
    fake = tmp_path / "falsa.key"
    fake.write_text(ECC.generate(curve="ed25519").export_key(format="PEM"))
    assert not lm.install_author_key(fake) and not lm.is_author
    real = tmp_path / "real.key"
    real.write_text(keypair)
    assert lm.install_author_key(real) and lm.is_author
    lm.log_issued("Ana", "AAAA-BBBB-CCCC-DDDD", "2027-04-05", "DGO1-x")
    lm.log_issued("Beto", "1111-2222-3333-4444", None, "DGO1-y")
    assert [i["nombre"] for i in lm.issued()] == ["Beto", "Ana"]
