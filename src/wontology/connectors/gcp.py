"""GCP Cloud Asset Inventory via Application Default Credentials."""

from __future__ import annotations

import re
import google.auth
from google.auth.transport.requests import AuthorizedSession

from .base import Collector

TYPES = {
    "compute.googleapis.com/Instance": "instances",
    "compute.googleapis.com/Network": "networks",
    "compute.googleapis.com/Subnetwork": "subnetworks",
    "compute.googleapis.com/Disk": "disks",
    "compute.googleapis.com/Firewall": "firewalls",
    "compute.googleapis.com/ForwardingRule": "forwarding_rules",
    "sqladmin.googleapis.com/Instance": "databases",
    "container.googleapis.com/Cluster": "container_clusters",
    "storage.googleapis.com/Bucket": "buckets",
    "run.googleapis.com/Service": "run_services",
}


def scan(options, publish, cancelled):
    project = options.get("project", "")
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]|[0-9]{6,20}", project):
        raise ValueError("Enter a valid GCP project ID or number")
    # Asset Inventory requires cloud-platform scope; IAM limits it to metadata reads.
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    c = Collector("gcp", project, publish, cancelled)
    with AuthorizedSession(credentials) as session:

        def fetch():
            token = None
            seen = set()
            while True:
                c.check()
                params = {"contentType": "RESOURCE", "pageSize": 500}
                if token:
                    params["pageToken"] = token
                response = session.get(
                    f"https://cloudasset.googleapis.com/v1/projects/{project}/assets",
                    params=params,
                    timeout=(5, 30),
                )
                if response.status_code == 403:
                    raise PermissionError("403")
                response.raise_for_status()
                payload = response.json()
                if "assets" in payload and not isinstance(payload["assets"], list):
                    raise ValueError("Invalid GCP inventory response")
                for asset in payload.get("assets", []):
                    data = dict(asset.get("resource", {}).get("data", {}))
                    key = TYPES.get(asset.get("assetType"), "resource_inventory")
                    data.update(
                        {
                            "assetType": asset.get("assetType"),
                            "fullResourceName": asset["name"],
                            "location": asset.get("resource", {}).get(
                                "location",
                                data.get("region", data.get("zone", "global")),
                            ),
                            "_source_api": "Cloud Asset Inventory.assets.list",
                        }
                    )
                    data["_inventory_key"] = key
                    yield data
                next_token = payload.get("nextPageToken")
                if not next_token:
                    break
                if next_token in seen:
                    raise ValueError("Repeated GCP continuation token")
                seen.add(next_token)
                token = next_token

        c.collect(
            "resource_inventory",
            "all",
            fetch,
            lambda row: c.inventory[row.pop("_inventory_key")].append(row),
        )
        return c.snapshot()
