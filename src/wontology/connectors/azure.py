"""Azure Resource Graph metadata, with nested subnets made explicit."""

from __future__ import annotations

import re
import requests
from azure.identity import DefaultAzureCredential

from .base import Collector

ENDPOINT = "https://management.azure.com/providers/Microsoft.ResourceGraph/resources?api-version=2024-04-01"
TYPES = {
    "microsoft.compute/virtualmachines": "virtual_machines",
    "microsoft.network/virtualnetworks": "virtual_networks",
    "microsoft.network/networkinterfaces": "network_interfaces",
    "microsoft.network/networksecuritygroups": "security_groups",
    "microsoft.network/loadbalancers": "load_balancers",
    "microsoft.compute/disks": "disks",
    "microsoft.dbforpostgresql/flexibleservers": "databases",
    "microsoft.containerservice/managedclusters": "container_clusters",
    "microsoft.storage/storageaccounts": "storage_accounts",
    "microsoft.web/sites": "web_apps",
}


def scan(options, publish, cancelled):
    subscription = options.get("subscription", "")
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", subscription):
        raise ValueError("Enter a valid Azure subscription ID")
    credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
    c = Collector("azure", subscription, publish, cancelled)
    try:

        def fetch():
            token = None
            seen = set()
            while True:
                c.check()
                body = {
                    "subscriptions": [subscription],
                    "query": "Resources | order by id asc",
                    "options": {"$top": 1000, "resultFormat": "objectArray"},
                }
                if token:
                    body["options"]["$skipToken"] = token
                access = credential.get_token(
                    "https://management.azure.com/.default"
                ).token
                response = requests.post(
                    ENDPOINT,
                    json=body,
                    headers={"Authorization": f"Bearer {access}"},
                    timeout=(5, 30),
                )
                if response.status_code == 403:
                    raise PermissionError("403")
                response.raise_for_status()
                data = response.json()
                if not isinstance(data.get("data"), list):
                    raise ValueError("Invalid Azure inventory response")
                for row in data["data"]:
                    yield {**row, "_source_api": "Azure Resource Graph.Resources"}
                next_token = data.get("$skipToken")
                if not next_token:
                    if str(data.get("resultTruncated", "false")).lower() == "true":
                        raise ValueError(
                            "Azure truncated results without a continuation token"
                        )
                    break
                if next_token in seen:
                    raise ValueError("Repeated Azure continuation token")
                seen.add(next_token)
                token = next_token

        # Collect once, then classify the dynamic inventory for relationship rules.
        def ingest(row):
            key = TYPES.get(str(row.get("type", "")).lower(), "resource_inventory")
            c.inventory[key].append(row)
            if key == "virtual_networks":
                for subnet in row.get("properties", {}).get("subnets", []):
                    c.inventory["subnets"].append(
                        {
                            **subnet,
                            "type": "Microsoft.Network/virtualNetworks/subnets",
                            "location": row.get("location"),
                            "parent_vnet_id": row["id"],
                            "_source_api": "Azure Resource Graph.Resources.properties.subnets",
                        }
                    )

        c.collect("resource_inventory", "all", fetch, ingest)
        return c.snapshot()
    finally:
        credential.close()
