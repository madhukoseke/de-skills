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

## Prompt caching

The canonical contract is large and largely static between requests. Every supported provider has a way to cache it so you only pay full input cost once per cache TTL. Each provider's optimization profile is also exported to `dist/<provider>/metadata.json` under the `optimization` key, so consumers can discover the right knob without reading this file.

| Provider | Mechanism | How to opt in | Notes |
|----------|-----------|---------------|-------|
| OpenAI / Codex | Automatic | Send the contract as the system message every call; identical prefixes ≥1024 tokens hit the cache. | No explicit flag needed; cache hit-rate visible in `usage.prompt_tokens_details.cached_tokens`. |
| Anthropic / Claude | Explicit (`cache_control: ephemeral`) | Wrap the contract as a system block with `cache_control: {"type": "ephemeral"}`. See [`examples/anthropic_messages_api.py`](../../../examples/anthropic_messages_api.py). | 5-minute TTL, ~10% of input cost on cache hit. Read counter in `usage.cache_read_input_tokens`. |
| Gemini | Explicit (`cachedContents`) | `POST /v1beta/cachedContents` with the contract as `systemInstruction`, then pass the returned cache name as `cachedContent` on each `generateContent`. | Default 1-hour TTL, configurable up to 24 h. Minimum content size applies (typically 32K tokens). |
| Generic runtime | None at provider | Cache the bundled `dist/<provider>/system_prompt.txt` in your assembly layer; the SHA in `metadata.json` lets you bust the cache only when the contract changes. | Verify the SHA matches `dist/adapter_index.json`. |

**Cost rule of thumb:** the contract is ~9KB / ~3K tokens. At ~$3/MTok input, an uncached request costs ≈ $0.009 in system-prompt tokens alone. Caching reduces that to ≈ $0.0009 per cached request, or zero for the generic case where the runtime owns the cache. For any consumer making >1 request/minute, prompt caching pays for itself immediately.

**Trade-offs:**
- Cached prompts are immutable across the TTL — bumping `contract_version` invalidates every consumer's cache. Schedule contract bumps during low-traffic windows.
- A cache miss (e.g., first request, TTL expired, model variant change) pays the full input cost plus a small write surcharge on Anthropic. Don't enable caching on workloads with <1 request per TTL window.
- Provider semantics differ: Anthropic charges for cache *writes* on first hit; Gemini charges hourly for cache *storage*; OpenAI charges nothing extra.

See also [`model_compatibility.md`](model_compatibility.md).
