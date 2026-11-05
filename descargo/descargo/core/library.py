"""Historial de descargas en SQLite (evita duplicados y permite buscar)."""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..utils import app_data_dir

_SCHEMA = """
CREATE TABLE IF NOT EXISTS downloads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT,
    url TEXT NOT NULL,
    title TEXT,
    platform TEXT,
    kind TEXT,
    quality TEXT,
    quality_key TEXT,
    filepath TEXT,
    size INTEGER,
    status TEXT,
    verdict TEXT,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_downloads_url ON downloads(url);
"""


@dataclass
class HistoryRow:
    id: int
    url: str
    title: str
    platform: str
    kind: str
    quality: str
    filepath: str
    size: int
    status: str
    verdict: str
    created_at: str


class Library:
    def __init__(self, path: Path | None = None):
        self.path = path or app_data_dir() / "historial.db"
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def add(self, *, job_id: str, url: str, title: str, platform: str, kind: str,
            quality: str, quality_key: str, filepath: str, size: int,
            status: str, verdict: str) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO downloads (job_id, url, title, platform, kind, quality, quality_key,"
                " filepath, size, status, verdict, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (job_id, url, title, platform, kind, quality, quality_key, filepath, size,
                 status, verdict, datetime.now().isoformat(timespec="seconds")),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def find_completed(self, url: str, quality_key: str) -> HistoryRow | None:
        """Devuelve una descarga anterior idéntica cuyo archivo todavía existe."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, url, title, platform, kind, quality, filepath, size, status, verdict,"
                " created_at FROM downloads WHERE url=? AND quality_key=? AND status='done'"
                " ORDER BY id DESC", (url, quality_key),
            ).fetchall()
        for row in rows:
            item = HistoryRow(*row)
            if item.filepath and Path(item.filepath).exists():
                return item
        return None

    def search(self, text: str = "", limit: int = 500) -> list[HistoryRow]:
        query = ("SELECT id, url, title, platform, kind, quality, filepath, size, status, verdict,"
                 " created_at FROM downloads")
        params: tuple = ()
        if text.strip():
            like = f"%{text.strip()}%"
            query += " WHERE title LIKE ? OR platform LIKE ? OR url LIKE ?"
            params = (like, like, like)
        query += " ORDER BY id DESC LIMIT ?"
        with self._lock:
            rows = self._conn.execute(query, params + (limit,)).fetchall()
        return [HistoryRow(*r) for r in rows]

    def delete(self, row_id: int) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM downloads WHERE id=?", (row_id,))
            self._conn.commit()

    def clear(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM downloads")
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()
