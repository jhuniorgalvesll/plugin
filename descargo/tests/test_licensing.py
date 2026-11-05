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


def test_summarize_clients_status_and_payments():
    from datetime import date, timedelta
    from descargo.core.licensing import summarize_clients
    today = date.today()
    entries = [
        {"fecha": "2026-01-01T10:00", "nombre": "Ana", "equipo": "aaaa-bbbb-cccc-dddd",
         "vence": (today - timedelta(days=3)).isoformat(), "licencia": "k1", "monto": 15},
        {"fecha": "2026-06-01T10:00", "nombre": "Ana Q.", "equipo": "AAAA-BBBB-CCCC-DDDD",
         "vence": (today + timedelta(days=150)).isoformat(), "licencia": "k2", "monto": 15},
        {"fecha": "2026-05-01T10:00", "nombre": "Beto", "equipo": "1111-2222-3333-4444",
         "vence": (today + timedelta(days=5)).isoformat(), "licencia": "k3", "monto": 10},
        {"fecha": "2026-04-01T10:00", "nombre": "Caro", "equipo": "9999-8888-7777-6666",
         "vence": None, "licencia": "k4"},
    ]
    clients = {c.name: c for c in summarize_clients(entries)}
    ana = clients["Ana Q."]                      # renovación: se agrupa por equipo
    assert ana.licenses == 2 and ana.total_paid == 30 and ana.last_key == "k2"
    assert ana.status()[0] == "active"
    assert clients["Beto"].status() == ("expiring", 5)
    assert clients["Caro"].status() == ("permanent", None)
    old = summarize_clients(entries[:1])[0]
    assert old.status()[0] == "expired"


def test_install_author_key_from_pasted_text(tmp_path, keypair):
    lm = LicenseManager(tmp_path)
    one_line = " ".join(keypair.split())          # pegado en una sola línea
    assert lm.install_author_key_text("  " + one_line + "  ") and lm.is_author
    other = LicenseManager(tmp_path / "x") if (tmp_path / "x").mkdir() is None else None
    fake = ECC.generate(curve="ed25519").export_key(format="PEM")
    assert not other.install_author_key_text(fake)
    assert not other.install_author_key_text("hola")
