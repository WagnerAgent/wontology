# Contributing to Wontology

Start with an issue describing the resource or relationship you want to support. Include synthetic examples or redacted shapes, never live credentials, private snapshots, or customer metadata.

Install development dependencies and run the commands in the README. Python tests must pass; frontend changes must typecheck and rebuild. Commit both frontend source and generated assets. Explain the behavior changed and how you checked it in your pull request.

For a connector change, test pagination, denied permissions, malformed responses, and empty accounts. For a relationship rule, test positive evidence and a plausible false match. Unknown or ambiguous references must remain unresolved. Keep metadata access explicit and read-only. Do not add cloud mutation or secret-value retrieval operations.

For UI changes, verify resource navigation and keyboard access on a desktop and a narrow viewport. Keep all required fonts, scripts, and assets local. No telemetry or mandatory AI providers.

Be respectful, specific, and constructive. Contributions are accepted under Apache-2.0. By contributing, you confirm you have the right to submit the work under this project's license.
