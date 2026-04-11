# Model Compatibility

This file documents tested or recommended model families for the provider adapters in `agents/`.

## OpenAI / Codex

- Adapter: `agents/openai.yaml`
- Recommended models:
  - `gpt-5`
  - `gpt-5.4`
  - `gpt-5.4-mini` for lower-cost benchmarking or lighter workloads
- Notes:
  - Strong structured markdown compliance in the benchmark harness
  - Handles long contracts well in the `system` channel
  - Lower-capability models may need tighter token budgets to preserve required headings

## Anthropic / Claude

- Adapter: `agents/anthropic.yaml`
- Recommended models:
  - `claude-sonnet-4-5`
  - `claude-opus-4-1`
- Notes:
  - Good at long-form reasoning and clarification-first behavior
  - May produce more prose around tables unless prompted with explicit formatting constraints
  - Keep the canonical contract in the `system` field, separate from user-pasted code or diffs

## Gemini

- Adapter: `agents/gemini.yaml`
- Recommended models:
  - `gemini-2.5-pro`
  - `gemini-2.5-flash` for lower-cost evaluation
- Notes:
  - Works best with `systemInstruction`
  - Formatting can vary more in long markdown outputs; benchmark against required headings before rollout
  - Smaller models may need shorter user prompts or generated bundles instead of raw markdown loading

## Generic Runtime

- Adapter: `agents/generic.yaml`
- Recommended use:
  - Any runtime with a high-priority system or developer channel
- Notes:
  - Prefer the generated `dist/generic/system_prompt.txt` artifact
  - Validate heading and clarification behavior before production use

## Known Quirks

- Long contracts plus long user diffs can exhaust smaller context windows.
- Providers differ in how reliably they preserve markdown tables under aggressive token limits.
- Clarification quality varies more by model family than by provider API shape; benchmark before defaulting a cheaper model in production.

For trimming prompts and contracts under tight token limits, see [`context_budget.md`](context_budget.md).
