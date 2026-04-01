# Generic Runtime Example

Use this pattern in any runtime that accepts a system or developer instruction block.

1. Load the canonical contract from `skills/data-engineering-best-practices/SKILL.md`, or use a generated provider bundle from `skills/data-engineering-best-practices/dist/`.
2. Put that content in the highest-priority instruction channel your runtime supports.
3. Send the user request as a normal user message.
4. Keep the contract separate from user-provided code, logs, links, or diffs.

Example structure:

```text
SYSTEM / DEVELOPER:
<contents of dist/generic/system_prompt.txt>

USER:
Design a daily CRM to warehouse pipeline for 20M rows/day with a 2-hour SLA.
```

Use the generated `dist/generic/system_prompt.txt` bundle when you want a stable, build-verified artifact instead of reading the canonical markdown directly.
