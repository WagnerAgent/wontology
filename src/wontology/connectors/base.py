"""Shared collection boundary: coverage is data, never an empty-account guess."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable
from threading import Event
from typing import Any

from wontology.ontology.spec_engine import SpecOntologyAdapter


class Cancelled(Exception):
    pass


SENSITIVE = re.compile(
    r"password|secret|token|private.?key|credential|api.?key|authorization|user.?data|connection.?string|environment",
    re.I,
)
VALUE_SECRET = re.compile(
    r"(?:AKIA|ASIA)[A-Z0-9]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----"
)


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(k): "[redacted]" if SENSITIVE.search(str(k)) else sanitize(v)
            for k, v in value.items()
            if str(k) != "raw"
        }
    if isinstance(value, list):
        return [sanitize(v) for v in value]
    if isinstance(value, str) and VALUE_SECRET.search(value):
        return "[redacted]"
    return value


class Collector:
    def __init__(self, provider: str, scope: str, publish: Callable, cancelled: Event):
        self.provider, self.scope = provider, scope
        self.inventory = defaultdict(list)
        self.coverage = []
        self.publish, self.cancelled = publish, cancelled

    def check(self):
        if self.cancelled.is_set():
            raise Cancelled("Scan cancelled")

    def collect(
        self, key: str, location: str, fetch: Callable, ingest: Callable | None = None
    ):
        self.check()
        rows = []
        try:
            for row in fetch():
                self.check()
                rows.append(row)
            record = {
                "service": key,
                "location": location,
                "status": "complete" if rows else "empty",
                "resources_found": len(rows),
            }
        except Cancelled:
            raise
        except Exception as exc:
            # Partial pages remain useful, but never count as full coverage.
            code = (
                getattr(exc, "response", {})
                .get("Error", {})
                .get(
                    "Code",
                    "AccessDenied"
                    if isinstance(exc, PermissionError)
                    else type(exc).__name__,
                )
            )
            status = (
                "access_denied"
                if any(
                    t in str(code).lower()
                    for t in ("denied", "forbidden", "unauthorized", "403")
                )
                else "failed"
            )
            record = {
                "service": key,
                "location": location,
                "status": status,
                "resources_found": len(rows),
                "error_code": str(code),
                "error_message": "Collection incomplete. Check cloud permissions, API availability, and credential expiry.",
            }
        if ingest:
            for row in rows:
                ingest(row)
        else:
            self.inventory[key].extend(rows)
        self.coverage.append(record)
        self.publish(self.snapshot(), record)

    def snapshot(self):
        snapshot = SpecOntologyAdapter(self.provider).build_snapshot(
            dict(self.inventory), cloud_scope_id=self.scope, coverage=self.coverage
        )
        value = snapshot.model_dump(mode="json")
        for resource in value["resources"]:
            resource["raw"] = {}
        return {**sanitize(value), "provider": self.provider, "scope": self.scope}
