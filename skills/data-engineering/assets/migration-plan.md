# Migration Plan: {CURRENT} to {TARGET}

## Outcomes and non-goals

{Business/engineering outcomes, success measures, and deliberate exclusions.}

## Current and target state

| Capability | Current evidence | Target | Gap/risk |
|---|---|---|---|
| {Contract/SLO/etc.} | {Fact} | {Target} | {Gap} |

## Compatibility and data movement

{Contracts, identity/key mapping, historical scope, schema/semantic conversion, security, and consumer changes.}

## Phases

1. Representative vertical pilot
2. Historical load and controlled catch-up
3. Shadow/dual-run with independent reconciliation
4. Consumer cohorts and canary cutover
5. Stability window and source freeze
6. Retirement, archival, access removal, and cost shutdown

## Gates and rollback

| Phase | Entry | Exit/reconciliation | Rollback trigger/action |
|---|---|---|---|
| {Phase} | {Condition} | {Condition} | {Action} |

## Ownership

{Producer, platform, security, consumer owners, communication, support, and final decommission approver.}
