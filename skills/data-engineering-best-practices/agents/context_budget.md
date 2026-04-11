# Context budget and truncation

Use this note when loading the canonical contract into **small context windows** or **low reasoning** models.

## Defaults

- Prefer generated bundles under `dist/<provider>/system_prompt.txt` over pasting all playbooks into the same prompt.
- Keep **user-supplied code, SQL, logs, and PR diffs** in the user channel only; never append them into the system contract.

## If you must trim the contract

1. Keep `SKILL.md` sections through **Trust Boundary** and **Non-Negotiable Principles** intact.
2. Drop lowest-priority playbooks first for the specific task (see **Mode selection (quick)** in `SKILL.md`).
3. Keep at least one relevant playbook for the active mode (e.g. **AIRFLOW** → `playbooks/02_airflow_reliability.md`).
4. When also emitting JSON, follow `schemas/skill_response.schema.json` and shrink `tradeOffs` / `nextSteps` before dropping `summary` or `decision`.

## Provider-specific hints

- **OpenAI / Codex** — Strong markdown compliance; reduce user-side attachments before shrinking the system contract.
- **Anthropic / Claude** — Long contracts work well in `system`; constrain table width in user prompts if responses run long.
- **Gemini** — Prefer `systemInstruction` + shorter user prompts; validate heading structure with the benchmark harness before rollout.

See also [`model_compatibility.md`](model_compatibility.md).
