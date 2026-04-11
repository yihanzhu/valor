# Security Policy

## Supported Scope

The active development target is the current `main` branch.

Security-relevant issues include:

- unintended data exfiltration
- privilege escalation through tool or install behavior
- unsafe defaults around local data handling
- command injection or path traversal in install and CLI flows
- corruption or unexpected exposure of local evidence data

## Reporting a Vulnerability

Please avoid posting sensitive details, credentials, internal code, or company
documents in a public issue.

Use GitHub private vulnerability reporting for this repository once it is
enabled.

Do not disclose undisclosed vulnerabilities in public issues, pull requests, or
discussions.

If private vulnerability reporting is temporarily unavailable, wait for a
private reporting path to be enabled before sharing sensitive details.

## Security Expectations for Contributions

Changes that affect privacy or security should:

- document any new data written to disk
- document any new network behavior
- preserve least-surprise defaults
- avoid making external access implicit or hard to audit

## Local-First Clarification

Valor is local-first, but it may run inside assistants or plugin environments
that use hosted models and networked integrations.

Please report security issues with the repo itself, and also note when a risk is
actually inherited from the surrounding assistant platform rather than from
Valor's code.
