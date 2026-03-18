# LLM / AI Cost Guardrails — OpenClaw

**Last updated:** 2026-03-18
**Status:** Guardrail spec. No LLM runtime usage exists today.

---

## 1. Current-state truth

**Zero LLM runtime usage.** OpenClaw does not call OpenAI, Anthropic, or any AI API at runtime. All scoring, classification, instructions, and priority_reason are deterministic Python rules. The runtime cost per lead is effectively zero (CPU + SQLite only).

The `.env.example` previously listed `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` — these were speculative placeholders, never wired to code.

**Where AI cost actually occurs:** Claude Code (this tool) is used for development. That cost is paid per conversation by the developer, not per lead by the application.

---

## 2. Task classification for future LLM use

### NEVER use LLM (must remain deterministic)

| Task | Why |
|---|---|
| Score calculation | Must be reproducible, auditable, instant. An LLM would add cost, latency, and non-determinism for no commercial gain. |
| Deduplication | Exact match on (email, source). LLM fuzzy matching would create false merges. |
| Action determination | Threshold-based. Must be instant and predictable for queue ordering. |
| Alert/rating computation | Same. |
| Auth / rate limiting | Obviously. |
| SQL queries / data access | Obviously. |
| Webhook normalization | Deterministic field mapping. LLM would add latency to every lead submission. |

### COULD use a cheap/fast model later (justify first)

| Task | Model tier | Trigger condition | Acceptable cost |
|---|---|---|---|
| Lead enrichment: extract structured data from free-text notes | Cheap (Haiku-class, < $0.001/lead) | Only for leads with score >= 60 AND notes contain unstructured text | < $0.01/lead, < 2s latency |
| Summary generation for lead pack | Cheap | Only on pack generation (on-demand, not on ingest) | Same |
| Email domain quality classification | Cheap or deterministic API | If deterministic heuristic proves insufficient | < $0.001/lead |
| Boat listing description generation | Cheap | Only for published listings, not lead intake | < $0.05/listing |

### MIGHT justify a stronger model later (high bar)

| Task | Model tier | Justification required |
|---|---|---|
| Market price estimation from boat specs | Mid-range | Only if it demonstrably improves scoring accuracy and operator trust |
| Competitor listing analysis | Mid-range | Only if it creates actionable competitive intelligence |
| Multi-language lead normalization | Mid-range | Only if non-Spanish leads become operationally significant |

---

## 3. Escalation rules

Before adding any LLM call to the runtime pipeline:

1. **Prove the deterministic version is insufficient.** Show concrete examples where the current rules fail commercially. "It would be better" is not enough — show leads that were mispriorized, lost, or mishandled because of the limitation.

2. **Measure the cost per lead.** Calculate: `(API cost per call) * (expected calls per day) * 30`. If the monthly cost exceeds the value of one lead, do not proceed.

3. **Measure the latency.** If the LLM call is in the hot intake path (webhook/form submission), it must complete in < 500ms. If it cannot, it must be async/deferred and not block the response.

4. **Define the fallback.** Every LLM call must have a deterministic fallback that runs if the API is down, slow, or returns garbage. The fallback IS the current deterministic behavior.

5. **Require approval.** Per CLAUDE.md: "Cambios en lógica de scoring" and "Cambios en autenticación, autorización, API keys" require human approval. LLM integration affects both (it's a new external dependency with a key).

---

## 4. Context discipline rules

When LLM calls are eventually added:

- **Minimal context.** Send only the fields needed for the task. Do not send the full lead record if only notes are needed.
- **No PII in prompts unless necessary.** Phone/email should not be sent to LLMs unless the task specifically requires them (e.g., email domain classification). Name alone is usually sufficient.
- **Cache aggressively.** If two leads have identical notes structure, reuse the result. Boat type classification for "Yate a motor" does not need to be re-inferred every time.
- **Batch when possible.** If enriching multiple leads, use batch APIs rather than one call per lead.
- **Log cost.** Every LLM call should log: model used, tokens in, tokens out, latency, lead_id. Without this, cost creep is invisible.

---

## 5. Anti-patterns to avoid

| Anti-pattern | Why it's bad | What to do instead |
|---|---|---|
| LLM scoring | Non-deterministic, expensive, slow, unexplainable to operator | Keep deterministic rules. Tune weights. |
| LLM for every lead | Cost scales linearly with volume. At 100 leads/day with $0.01/lead = $30/month for questionable value | Only enrich leads above a score threshold |
| LLM in the hot intake path | Adds 1-3s latency to form submission. User sees spinner. API timeout risk. | Process async, update lead after ingest |
| Using GPT-4 / Opus for simple classification | 10-50x cost of Haiku for a task that doesn't need it | Use the cheapest model that works. Benchmark first. |
| Sending full notes + all fields to LLM | Wastes tokens on irrelevant context | Send only the specific field being processed |
| LLM without fallback | API outage = broken pipeline | Always have deterministic fallback |
| LLM results stored without the model version | Can't reproduce or audit results later | Log model ID + version with every stored LLM result |
| "Let the AI figure it out" prompts | Unreliable, expensive, untestable | Structured prompts with explicit output format |

---

## 6. What should remain intentionally unbuilt

| Capability | Why not build it |
|---|---|
| Token usage dashboard | No tokens to track. Build when first LLM integration ships. |
| Model routing layer | One model per task is sufficient until there are 3+ LLM tasks. |
| Cost budget / circuit breaker | Premature. First LLM task will have its own cost cap. |
| LLM-based scoring | Deterministic scoring works and is free. Do not replace it. |
| Prompt management system | No prompts exist. One hardcoded prompt per task is fine for MVP. |
| Embedding / vector search | No use case yet. Lead search is SQL LIKE, which works. |

---

## 7. First LLM integration candidate (when ready)

The highest-ROI first LLM use would be **structured extraction from free-text notes** for leads with `score >= 60`:

```
Input:  "Azimut 50, 2018, 15m, El Masnou, teca nueva, un motor cuesta arrancar"
Output: { "marca": "Azimut", "modelo": "50", "año": 2018, "eslora_m": 15, "puerto": "El Masnou" }
```

This would:
- Improve scoring accuracy (eslora, price, brand parsed reliably)
- Improve operator display (structured fields instead of raw text)
- Cost: ~$0.001/lead with Haiku-class model
- Trigger: only for high-value leads (score >= 60), not universal

**Do not build this until:** (a) there are 50+ leads with free-text that the deterministic parser misses, and (b) the operator confirms that missed parsing actually causes commercial problems.
