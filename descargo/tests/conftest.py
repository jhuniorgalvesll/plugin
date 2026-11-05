import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def isolated_app_data(tmp_path, monkeypatch):
    """Cada prueba usa su propia carpeta de datos (no toca la del usuario)."""
    data = tmp_path / "appdata"
    data.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(data))
    monkeypatch.setenv("APPDATA", str(data))
    return data
