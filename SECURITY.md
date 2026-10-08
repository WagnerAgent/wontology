# Security

Wontology 0.1.x is a local, single-user application. It is not designed to be exposed to the Internet or used as a shared unauthenticated service.

- Bind to localhost. In Docker, publish `127.0.0.1:8787:8787`.
- Prefer temporary cloud credentials and identities restricted to configuration metadata.
- The browser receives credential references such as profile names; it never accepts cloud secret keys.
- SDKs may read credentials from local configuration, environment variables, or provider identity services according to their standard credential chain.
- No cloud write operations, deployment, secret-value reads, or data-content retrieval are implemented.
- Snapshot files are protected with local file permissions where supported, not application encryption. Use encrypted disk storage when appropriate.
- Redaction is best effort. Names, IDs, tags, and configuration properties can be confidential even without credentials. Review exports manually before sharing.
- Imported graphs are validated, bounded in size, and rendered as text. They are not executed.
- Local Host/Origin checks and an automatic browser session cookie help prevent cross-site requests and DNS rebinding. They do not protect against a compromised local machine or browser.

Report vulnerabilities privately through GitHub's **Report a vulnerability** feature on this repository. Do not publish credentials, tokens, private snapshots, or exploit details in a public issue. If private reporting is unavailable, open an issue containing only a request for a private reporting channel.

Cloud SDKs, inventory APIs, and the frontend dependencies follow their own security advisories. The lockfiles identify the versions used for release validation.
