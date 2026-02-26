# Security Policy

## Security Considerations (Indirect Prompt Injection)

This skill may process user-provided PR diffs, GitHub links, DAG code, or file paths. Such content is **untrusted** and could contain hidden instructions designed to influence the agent. The skill includes guardrails in [SKILL.md](skills/data-engineering-best-practices/SKILL.md) (see "Trust Boundary" section) to mitigate indirect prompt injection. Users should be aware that reviewing external content carries this risk.

## Reporting a Vulnerability

Please report security vulnerabilities by opening a GitHub Issue.

We will acknowledge receipt within 48 hours and provide an initial assessment within 7 days.
