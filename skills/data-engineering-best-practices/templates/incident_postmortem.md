---
title: "Incident Postmortem"
description: "Template for data pipeline incident postmortem with 5 Whys framework"
tags: [postmortem, incident, root-cause-analysis, template]
---

# Incident Postmortem: {INCIDENT_TITLE}

**Incident ID:** {ID}
**Date:** {YYYY-MM-DD}
**Severity:** {P1 / P2 / P3 / P4}
**Status:** {draft / reviewed / closed}
**Author:** {NAME}
**Reviewers:** {NAMES}

## Timeline

All times in UTC.

| Time | Event |
|------|-------|
| {HH:MM} | {First symptom detected / alert fired} |
| {HH:MM} | {On-call acknowledged} |
| {HH:MM} | {Root cause identified} |
| {HH:MM} | {Mitigation applied} |
| {HH:MM} | {Service restored} |
| {HH:MM} | {Verification complete} |

**Time to detect (TTD):** {minutes}
**Time to mitigate (TTM):** {minutes}
**Time to resolve (TTR):** {minutes}
**Total downtime:** {minutes/hours}

## Impact

| Dimension | Detail |
|-----------|--------|
| Data affected | {tables, date ranges, row counts} |
| Data loss | {Yes/No — if yes, quantify} |
| Data correctness | {Were incorrect records served to consumers?} |
| Downstream impact | {Which consumers/dashboards/models were affected} |
| SLA breach | {Yes/No — if yes, which SLA} |
| Customer impact | {External customer impact, if any} |
| Financial impact | {Estimated cost: compute waste, business impact} |

## What Happened

{2-3 paragraph narrative of the incident. Include:}
- What was the expected behavior?
- What actually happened?
- How was the incident detected?
- What was the immediate response?

## Root Cause

{1-2 paragraphs describing the technical root cause.}

## 5 Whys Analysis

Work backwards from the symptom to the root cause. Each "Why" should be a factual statement, not speculation.

| # | Question | Answer |
|---|----------|--------|
| 1 | Why did {symptom} occur? | Because {direct cause} |
| 2 | Why did {direct cause} happen? | Because {underlying cause 1} |
| 3 | Why did {underlying cause 1} happen? | Because {underlying cause 2} |
| 4 | Why did {underlying cause 2} happen? | Because {underlying cause 3} |
| 5 | Why did {underlying cause 3} happen? | Because {root cause} |

**Root cause category:** {Code bug / Configuration error / Infrastructure failure / Schema change / Dependency failure / Capacity / Human error / Process gap}

## What Went Well

- {Things that worked during incident response}
- {Detection that fired correctly}
- {Team actions that reduced impact}

## What Went Wrong

- {Things that increased impact or delayed resolution}
- {Missing monitoring or alerts}
- {Process gaps}

## Where We Got Lucky

- {Things that could have made this worse but didn't}
- {Near-misses that this incident revealed}

## Action Items

| # | Action | Owner | Priority | Due Date | Status | Ticket |
|---|--------|-------|----------|----------|--------|--------|
| 1 | {Immediate fix applied during incident} | {name} | P0 | {date} | Done | {link} |
| 2 | {Prevention: ensure this specific failure can't recur} | {name} | P1 | {date} | TODO | {link} |
| 3 | {Detection: improve monitoring to catch this faster} | {name} | P1 | {date} | TODO | {link} |
| 4 | {Process: update runbook/documentation} | {name} | P2 | {date} | TODO | {link} |
| 5 | {Broader: systemic improvement to prevent similar class of issues} | {name} | P2 | {date} | TODO | {link} |

### Action Item Categories

Ensure at least one action item in each category:

- **Prevent:** Stop this specific failure from recurring
- **Detect:** Catch this failure faster if it happens again
- **Mitigate:** Reduce the blast radius if it happens again
- **Process:** Update runbooks, documentation, or team processes

## Lessons Learned

{Key takeaways that the broader team should internalize. Focus on systemic insights, not blame.}

1. {Lesson 1}
2. {Lesson 2}
3. {Lesson 3}

## Related Incidents

| Incident | Date | Similarity |
|----------|------|------------|
| {ID} | {date} | {How it relates} |

## Appendix

### Relevant Queries Used During Investigation

```sql
-- {Description of what this query checks}
{SQL query used during diagnosis}
```

### Relevant Logs

```
{Key log entries that helped identify the root cause}
```

### Configuration Changes Made

```
{Any config changes applied as part of mitigation}
```
