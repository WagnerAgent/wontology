# Coverage and limitations

## Initial release

All connectors are deterministic. They inspect configuration metadata; they do not capture traffic, agent telemetry, database queries, source code, or application traces. Unknown resources remain visible with a generic classification. Unknown health remains unknown.

AWS performs the explicit calls declared in `connectors/aws.py`, across selected regions. EC2 instances, VPCs, subnets, security groups, volumes, route tables, gateways, load balancers, Lambda, RDS, ECR, SNS, logs, KMS, S3, and IAM roles are collected. SDK pagination is followed to completion. Other AWS services and nested resources not listed here are not collected. S3 buckets are currently shown at global scope.

Azure lists Resource Graph's `Resources` table and expands nested VNet subnets. GCP lists Cloud Asset Inventory resources. Both inventory services have provider-specific coverage, visibility, and freshness limits. Resource properties that the inventory service does not expose are not hydrated through additional service calls in 0.1.0. Consequently, some relationships remain unresolved or absent.

Read `ontology/specs/*.yaml` for the exact relationship rules. A rule only creates an edge when both endpoints are discovered and the configuration contains a matching reference. Ambiguous aliases are left unresolved, never attached to a guessed resource.

## Coverage status

- `complete`: the configured collector finished successfully.
- `empty`: the configured collector succeeded and returned no resources.
- `access_denied`: the provider rejected a read.
- `failed`: timeout, expired credentials, malformed response, repeated pagination token, or another incomplete collection.
- `unsupported` and `partial`: reserved for more detailed adapters.

This is collector coverage, not a claim of full provider coverage. Permission-filtered inventory can omit inaccessible resources without an error. Partial scans remain queryable and cannot replace the saved last-complete scan. The SQLite store preserves all saved scans; it does not infer deletions from missing resources in a partial scan.

## Validation

Automated tests use synthetic graph fixtures and mocked provider responses, including pagination, partial failure, redaction, stable identities, graph validation, and the local HTTP boundary. Browser verification covers example switching, region/network/service/resource drill-down, breadcrumbs, the resource atlas, resource inspection, search, grouping, connection fields, and desktop/mobile layouts. No live customer cloud accounts were scanned as part of initial publication.

## Current boundaries

- One cloud scope per snapshot; no automatic cross-cloud stitching.
- AWS regions are selected explicitly.
- First Azure/GCP graph appears after inventory collection, rather than per page.
- Scans are sequential within a provider; cancellation is cooperative between requests, which have bounded timeouts.
- No external AI, automated provisioning, SaaS billing, or team accounts.
- JSON import is limited to 8 MiB, 20,000 resources, and 100,000 relationships.
- The navigable canvas groups resources into observed region/network/service scopes; the atlas shows up to 2,000 cells and each service view up to 240 resources. Search reaches all resources, displaying up to 30 matches at a time.
- In full topology, above 300 matching resources, the diagram aggregates by semantic type and location. Search and filters narrow the graph.
- Network membership is a presentation projection of explicit containment, deployment, and attachment evidence. Missing membership stays unassigned; multiple memberships are labeled. Grouped curves aggregate observed relationships, while the inspector retains their exact kinds and evidence.
- SVG and JSON export are available. PNG export, manual annotations, and rich snapshot comparison are planned.
- Local SQLite snapshots are not encrypted by the application.
