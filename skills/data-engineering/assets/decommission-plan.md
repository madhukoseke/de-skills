# Decommission Plan: {SYSTEM_OR_DATASET}

## Decision and evidence

{Why retirement is safe, replacement if any, usage/lineage evidence, owner and approver.}

## Consumer exit

| Consumer | Owner | Replacement/action | Validation | Deadline |
|---|---|---|---|---|
| {Consumer} | {Owner} | {Action} | {Evidence} | {Date} |

## Retention and legal obligations

{Archive, retention, legal hold, deletion, audit, export, and restore requirements.}

## Shutdown sequence

1. Announce deprecation and block new consumers.
2. Validate zero required reads/writes and complete replacement reconciliation.
3. Disable producers/schedules, then consumers/endpoints.
4. Revoke access and credentials; remove alerts after the observation window.
5. Archive/delete data and infrastructure according to policy.
6. Verify billing, catalog, lineage, DNS/routes, and support references are removed.

## Rollback window

{Re-enable/switchback method, retained artifacts/data, expiry, and final irreversible step.}
