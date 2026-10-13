# Architecture

```mermaid
flowchart LR
    A[Local cloud credential chain] --> B[Explicit metadata collectors]
    B --> C[Provider inventory and coverage]
    C --> D[YAML ontology rules]
    D --> E[Validated snapshot]
    E --> F[Local SQLite store]
    E --> G[Same-origin local API]
    G --> H[React Flow explorer]
```

`wontology` starts a loopback HTTP server and opens the browser. The initial synthetic example does not initialize cloud credentials. A scan request starts a background thread for a single selected provider scope. Connector modules define all callable operations; there is no arbitrary cloud API dispatcher or shell command execution.

The ontology layer combines a typed graph model, provider registry, YAML normalization, classification, and projection code. The React UI provides hierarchical canvas navigation and a React Flow full topology view. Python serves the static esbuild bundle alongside the local API, so users do not need a separate frontend server or a hosted service.

Every relationship carries evidence, rule identity, confidence, and observation time. Authoritative snapshots reject duplicate identities, dangling edges, inferred edges, and edges without evidence. Alias ambiguity stays unresolved. Snapshot and bundle versions allow exported graphs to be interpreted reproducibly.

The local persistence layer saves immutable snapshots. A query for last-complete state ignores partial scans. The server currently permits one active scan; it returns progress snapshots through polling. Credentials stay in the cloud SDK/runtime credential chain and are not stored in SQLite. Raw payload fields are dropped and selected sensitive metadata keys are redacted before persistence.

The local server rejects unexpected Host and Origin headers, requires JSON for mutations, and assigns an automatic HttpOnly SameSite=Strict cookie to the local browser. This protects the local cloud-reading surface without introducing a user identity or login screen. It is not a remote multi-user authentication mechanism.

The UI and all assets are served locally. The public source link and attribution links navigate externally only when clicked.
