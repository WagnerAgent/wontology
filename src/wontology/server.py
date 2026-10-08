"""Same-origin local application server with explicit cloud scan endpoints."""

from __future__ import annotations

import importlib
import json
import os
import secrets
import threading
import webbrowser
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from uuid import uuid4

from .connectors.base import Cancelled, sanitize
from .demo import demo
from .ontology.models import OntologySnapshot
from .store import Store

PROVIDERS = {"aws", "azure", "gcp"}
MAX_BODY = 8 * 1024 * 1024


class Application:
    def __init__(self, data_dir):
        self.store = Store(Path(data_dir) / "snapshots.sqlite3")
        self.jobs, self.cancelled = {}, {}
        self.lock = threading.RLock()
        self.session = secrets.token_urlsafe(32)

    def start(self, options):
        provider = options.get("provider")
        if provider not in PROVIDERS:
            raise ValueError("Choose AWS, Azure, or GCP")
        # Connection references only; never accept pasted cloud secrets.
        if set(options) - {"provider", "profile", "regions", "subscription", "project"}:
            raise ValueError(
                "Only local credential references and cloud scopes are accepted"
            )
        for key in ("profile", "subscription", "project"):
            if key in options and (
                not isinstance(options[key], str) or len(options[key]) > 200
            ):
                raise ValueError(f"Invalid {key}")
        regions = options.get("regions", [])
        if (
            not isinstance(regions, list)
            or len(regions) > 40
            or any(not isinstance(r, str) or len(r) > 40 for r in regions)
        ):
            raise ValueError("Invalid regions")
        with self.lock:
            if any(j["status"] == "running" for j in self.jobs.values()):
                raise ValueError(
                    "A scan is already running. Cancel it or wait for it to finish."
                )
            identifier = str(uuid4())
            self.jobs[identifier] = {
                "id": identifier,
                "provider": provider,
                "status": "running",
                "snapshot": None,
                "progress": None,
            }
            self.cancelled[identifier] = threading.Event()
        threading.Thread(
            target=self._scan, args=(identifier, options), daemon=True
        ).start()
        return {"id": identifier}

    def _scan(self, identifier, options):
        def publish(snapshot, progress):
            with self.lock:
                self.jobs[identifier].update(snapshot=snapshot, progress=progress)

        try:
            connector = importlib.import_module(
                f"wontology.connectors.{options['provider']}"
            )
            snapshot = connector.scan(options, publish, self.cancelled[identifier])
            if self.cancelled[identifier].is_set():
                raise Cancelled()
            scope = (
                snapshot.get("scope")
                or next(iter(snapshot.get("resources", [])), {}).get("cloud_scope_id")
                or options.get("subscription")
                or options.get("project")
                or "aws-account"
            )
            saved = self.store.save(snapshot, options["provider"], scope)
            with self.lock:
                self.jobs[identifier].update(
                    status="complete" if saved["complete"] else "partial",
                    snapshot=saved,
                )
        except Cancelled:
            with self.lock:
                self.jobs[identifier]["status"] = "cancelled"
        except Exception as exc:
            # Provider exception text can include tokens. Return a safe action message.
            with self.lock:
                self.jobs[identifier].update(
                    status="failed",
                    error=f"{type(exc).__name__}: Could not scan. Check your local cloud session, scope, enabled APIs, and metadata permissions.",
                )


class Handler(BaseHTTPRequestHandler):
    server_version = "Wontology"

    def log_message(self, *_):
        pass

    @property
    def app(self):
        return self.server.app

    def send(self, value, status=200, content_type="application/json", cookie=False):
        data = value if isinstance(value, bytes) else json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
        )
        if cookie:
            self.send_header(
                "Set-Cookie",
                f"wontology_session={self.app.session}; HttpOnly; SameSite=Strict; Path=/",
            )
        self.end_headers()
        self.wfile.write(data)

    def trusted(self, api=False):
        # Reject DNS rebinding and other local websites initiating cloud access.
        expected = {
            f"localhost:{self.server.server_port}",
            f"127.0.0.1:{self.server.server_port}",
        }
        if self.headers.get("Host") not in expected:
            self.send({"error": "Invalid host"}, 403)
            return False
        origin = self.headers.get("Origin")
        if origin and origin not in {f"http://{host}" for host in expected}:
            self.send({"error": "Invalid origin"}, 403)
            return False
        if api:
            cookie = SimpleCookie()
            try:
                cookie.load(self.headers.get("Cookie", ""))
            except Exception:
                self.send({"error": "Open Wontology in your browser first"}, 403)
                return False
            token = cookie.get("wontology_session")
            if not token or not secrets.compare_digest(token.value, self.app.session):
                self.send({"error": "Open Wontology in your browser first"}, 403)
                return False
        return True

    def do_GET(self):
        path = urlparse(self.path).path
        if not self.trusted(api=path.startswith("/api/")):
            return
        try:
            if path == "/api/demo":
                provider = parse_qs(urlparse(self.path).query).get("provider", ["aws"])[
                    0
                ]
                return self.send(demo(provider))
            if path == "/api/profiles":
                import boto3

                try:
                    profiles = boto3.Session().available_profiles
                except Exception:
                    profiles = []
                return self.send(
                    {
                        "aws": profiles,
                        "gcp_project": os.getenv("GOOGLE_CLOUD_PROJECT", ""),
                    }
                )
            if path == "/api/snapshots":
                return self.send(self.app.store.list())
            if path.startswith("/api/snapshots/"):
                value = self.app.store.get(path.rsplit("/", 1)[-1])
                return self.send(
                    value or {"error": "Snapshot not found"}, 200 if value else 404
                )
            if path.startswith("/api/scans/"):
                with self.app.lock:
                    value = self.app.jobs.get(path.rsplit("/", 1)[-1])
                    return self.send(
                        value or {"error": "Scan not found"}, 200 if value else 404
                    )
            if path.startswith("/api/"):
                return self.send({"error": "Not found"}, 404)
            name = "index.html" if path == "/" else path.lstrip("/")
            if name not in {
                "index.html",
                "app.js",
                "app.css",
                "favicon.svg",
                "app.js.LEGAL.txt",
            } | {
                f"fonts/{name}" for name in (
                    "Inter.ttf", "SpaceGrotesk-Regular.ttf", "InstrumentSerif-Regular.ttf",
                    "inter-OFL.txt", "spacegrotesk-OFL.txt", "instrumentserif-OFL.txt",
                )
            } | {f"icons/{name}.svg" for name in ("compute", "database", "generic", "network")}:
                return self.send({"error": "Not found"}, 404)
            mime = {
                "html": "text/html; charset=utf-8",
                "js": "text/javascript",
                "css": "text/css",
                "svg": "image/svg+xml",
                "txt": "text/plain; charset=utf-8",
                "ttf": "font/ttf",
            }[name.rsplit(".", 1)[-1]]
            return self.send(
                files("wontology").joinpath("static", name).read_bytes(),
                content_type=mime,
                cookie=name == "index.html",
            )
        except (ValueError, KeyError):
            return self.send({"error": "Invalid request"}, 400)

    def do_POST(self):
        if not self.trusted(api=True):
            return
        try:
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                return self.send({"error": "JSON required"}, 415)
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > MAX_BODY:
                return self.send(
                    {"error": "Body must be between 1 byte and 8 MiB"}, 413
                )
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError("Expected JSON object")
            path = urlparse(self.path).path
            if path == "/api/scans":
                return self.send(self.app.start(body), 202)
            if path.startswith("/api/scans/") and path.endswith("/cancel"):
                with self.app.lock:
                    event = self.app.cancelled.get(path.split("/")[3])
                    if event:
                        event.set()
                return self.send({"cancelled": bool(event)}, 200 if event else 404)
            if path == "/api/import":
                if (
                    len(body.get("resources", [])) > 20000
                    or len(body.get("relationships", [])) > 100000
                ):
                    raise ValueError("Snapshot exceeds import limits")
                value = OntologySnapshot.model_validate(body).model_dump(mode="json")
                providers = {r["provider"] for r in value["resources"]}
                scopes = {r["cloud_scope_id"] for r in value["resources"]}
                provider = body.get("provider") or next(iter(providers), None)
                if (
                    provider not in PROVIDERS
                    or len(providers) > 1
                    or len(scopes) > 1
                    or (providers and providers != {provider})
                ):
                    raise ValueError("Import one provider and cloud scope per snapshot")
                return self.send(
                    self.app.store.save(
                        sanitize(value),
                        provider,
                        next(iter(scopes), body.get("scope", "imported")),
                    ),
                    201,
                )
            return self.send({"error": "Not found"}, 404)
        except (ValueError, KeyError, TypeError):
            return self.send(
                {"error": "Invalid request. Check cloud scope or snapshot schema."}, 400
            )


def run(port, data_dir, open_browser=True, container=False):
    server = ThreadingHTTPServer(
        ("0.0.0.0" if container else "127.0.0.1", port), Handler
    )
    server.daemon_threads = True
    server.app = Application(data_dir)
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"Wontology is ready: {url}\nSnapshots stay in {data_dir}", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        for event in server.app.cancelled.values():
            event.set()
        server.server_close()
