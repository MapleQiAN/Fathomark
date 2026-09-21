# Security policy

## Scope

Please report vulnerabilities that could expose credentials, bypass approval
or immutability guarantees, cause server-side request forgery, execute hostile
document content, corrupt evidence provenance, or disclose another user's
research data. The project is pre-1.0; the local Docker demo is not a hardened
internet-facing deployment.

## Reporting

Do not open a public issue for an undisclosed vulnerability. Use the repository
security-advisory flow on GitHub or contact the maintainers privately with a
description, affected commit, reproduction steps, impact, and a safe fix
window. Do not include API keys, paid data, personal data, or production
records in a report.

We will acknowledge a report within seven days, triage severity and affected
versions, and coordinate disclosure after a fix or mitigation is available.

## Deployment controls

- Keep `DATABASE_URL`, provider keys, webhook secrets, and user-agent values in
  environment or a secret manager; never commit them or put them in cassettes.
- Put the API behind authentication, TLS, network policy, rate limits, and an
  allowlist before exposing it beyond a trusted local network.
- Treat provider URLs and document text as hostile input. Validate schemes and
  destinations, enforce timeouts and response-size limits, and do not let
  retrieved text become executable instructions.
- Keep deterministic scoring and approval in the host. Plugins and agents must
  return validated contracts and must not write the core database directly.
- Review dependency and container updates; run the repository test, lint and
  vulnerability checks before release.
