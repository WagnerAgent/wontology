"""Local immutable snapshots, with last-complete state kept across partial scans."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class Store:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS snapshots (id TEXT PRIMARY KEY, provider TEXT NOT NULL, scope TEXT NOT NULL, created_at TEXT NOT NULL, complete INTEGER NOT NULL, payload TEXT NOT NULL)"
            )
        os.chmod(path, 0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            with db:
                yield db
        finally:
            db.close()

    def save(self, snapshot, provider, scope):
        identifier, now = str(uuid4()), datetime.now(timezone.utc).isoformat()
        complete = bool(snapshot.get("coverage")) and all(
            r["status"] in ("complete", "empty") for r in snapshot["coverage"]
        )
        value = {
            **snapshot,
            "id": identifier,
            "provider": provider,
            "scope": scope,
            "created_at": now,
            "complete": complete,
        }
        with self.connect() as db:
            db.execute(
                "INSERT INTO snapshots VALUES (?, ?, ?, ?, ?, ?)",
                (identifier, provider, scope, now, int(complete), json.dumps(value)),
            )
        return value

    def list(self):
        with self.connect() as db:
            return [
                dict(zip(("id", "provider", "scope", "created_at", "complete"), row))
                for row in db.execute(
                    "SELECT id, provider, scope, created_at, complete FROM snapshots ORDER BY created_at DESC LIMIT 100"
                )
            ]

    def get(self, identifier):
        with self.connect() as db:
            row = db.execute(
                "SELECT payload FROM snapshots WHERE id = ?", (identifier,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def last_complete(self, provider, scope):
        with self.connect() as db:
            row = db.execute(
                "SELECT payload FROM snapshots WHERE provider=? AND scope=? AND complete=1 ORDER BY created_at DESC LIMIT 1",
                (provider, scope),
            ).fetchone()
        return json.loads(row[0]) if row else None
