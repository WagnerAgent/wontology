import json
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

import pytest

from wontology.demo import demo
from wontology.server import Application, Handler
from wontology.store import Store


def test_partial_snapshot_keeps_last_complete(tmp_path):
    store = Store(tmp_path / "graph.sqlite3")
    complete = store.save(demo(), "aws", "000000000000")
    partial = demo()
    partial["coverage"][0]["status"] = "access_denied"
    store.save(partial, "aws", "000000000000")
    assert len(store.list()) == 2
    assert store.last_complete("aws", "000000000000")["id"] == complete["id"]


@pytest.fixture
def server(tmp_path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.app = Application(tmp_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join()


def request(server, path, method="GET", body=None, headers=None):
    conn = HTTPConnection("127.0.0.1", server.server_port)
    conn.request(method, path, body, headers or {})
    response = conn.getresponse()
    value = (response.status, dict(response.getheaders()), response.read())
    conn.close()
    return value


def test_no_login_bootstrap_and_all_three_examples(server):
    status, headers, _ = request(server, "/")
    assert status == 200
    assert "SameSite=Strict" in headers["Set-Cookie"]
    cookie = headers["Set-Cookie"].split(";")[0]
    for provider in ("aws", "azure", "gcp"):
        status, _, data = request(
            server, f"/api/demo?provider={provider}", headers={"Cookie": cookie}
        )
        assert status == 200
        assert json.loads(data)["provider"] == provider


@pytest.mark.parametrize(
    "headers", [{"Host": "attacker.example"}, {"Origin": "https://attacker.example"}]
)
def test_local_server_rejects_other_origins_and_hosts(server, headers):
    assert request(server, "/", headers=headers)[0] == 403


def test_api_requires_automatic_local_session(server):
    assert request(server, "/api/snapshots")[0] == 403


def test_import_validates_graph_and_redacts_sensitive_fields(server):
    _, headers, _ = request(server, "/")
    cookie = headers["Set-Cookie"].split(";")[0]
    value = demo()
    value["resources"][0]["properties"]["password"] = "should-not-survive"
    headers = {"Cookie": cookie, "Content-Type": "application/json"}
    status, _, data = request(server, "/api/import", "POST", json.dumps(value), headers)
    assert status == 201
    assert b"should-not-survive" not in data
    value["relationships"][0]["target_id"] = "missing"
    assert request(server, "/api/import", "POST", json.dumps(value), headers)[0] == 400


def test_raw_cloud_credentials_not_accepted(tmp_path):
    app = Application(tmp_path)
    with pytest.raises(ValueError):
        app.start({"provider": "aws", "secret_access_key": "example"})


def test_static_path_traversal_rejected(server):
    assert request(server, "/../pyproject.toml")[0] == 404
