# MemoryBench human audit sample (job `3b31e5e3`)

Author: Mohamed Kamil Bourouiba · Date: 26 June 2026

## Protocol

Five stratified scenarios were reviewed against ingested episodes and expected concepts.
Each row compares the **LLM judge** (retention $\geq 0.7$ pass) with a **keyword rubric**
(concept overlap $\geq 0.5$). The author read `answer_preview` + `judge_reasoning` from the
persisted export (`GET /api/v1/benchmark/export`) and confirmed judge direction.

**Keyword–judge agreement on retention pass/fail:** 4/5 scenarios.

## Scenario sample

### `retention_latency_churn`

- Judge retention: **1.0** · groundedness: **1.0**
- Keyword retention: **1.0** · pass agreement: **True**
- Preview: Customers churn primarily due to repeated performance issues, especially high latency in key product features such as dashboard loads, checkout, or API responses. Slow performance, timeouts, and laten…
- Judge note: The answer accurately captures the reference concepts of latency, churn, and performance, using synonymous phrases like 'high latency', 'slow performance', and 'timeouts'. It is fully grounded in the ingested episodes, which directly link customer churn to latency and performance…

### `contradiction_handling`

- Judge retention: **1.0** · groundedness: **1.0**
- Keyword retention: **1.0** · pass agreement: **True**
- Preview: Yes, latency causes churn.…
- Judge note: The answer directly states that latency causes churn, which matches the reference concepts of latency, churn, and a causal link. The ingested episode explicitly supports this causal relationship, so the answer is fully grounded.…

### `hallucination_resistance`

- Judge retention: **1.0** · groundedness: **1.0**
- Keyword retention: **0.0** · pass agreement: **False**
- Preview: There is no evidence in the provided memory context that customers churned because of dark mode. All available abstractions and episodes associate customer churn with performance issues such as high l…
- Judge note: The answer accurately states that there is no evidence linking customer churn to the dark mode feature, which matches the provided episodes. It correctly grounds churn to performance issues, not dark mode, and does not introduce unsupported claims.…

### `feedback_belief_adjustment`

- Judge retention: **1.0** · groundedness: **1.0**
- Keyword retention: **0.5** · pass agreement: **True**
- Preview: Discounts reduce churn, particularly in price-sensitive segments.…
- Judge note: The answer directly matches the ingested episode, stating that discounts reduce churn in price-sensitive segments. Both reference concepts, pricing (discounts) and churn, are addressed. The claim is fully supported by the ingested episode.…

### `multi_source_conflict`

- Judge retention: **1.0** · groundedness: **1.0**
- Keyword retention: **1.0** · pass agreement: **True**
- Preview: Churn in enterprise accounts is primarily driven by latency and performance incidents, while churn in SMB segments is primarily driven by pricing changes.…
- Judge note: The answer accurately captures the reference concepts: it links churn in enterprise to latency/performance incidents and churn in SMB to pricing changes, matching the ingested episodes. There are no unsupported claims or hallucinations.…

## Cross-scenario judge validity (ACME, n=13)

- Pearson *r* (LLM retention vs keyword retention): **n/a**
- retention: mean **1.0** [1.0, 1.0] (bootstrap 95% CI)
- groundedness: mean **1.0** [1.0, 1.0] (bootstrap 95% CI)
- feedback: mean **1.0** [1.0, 1.0] (bootstrap 95% CI)
- belief: mean **0.7** [0.7, 0.7] (bootstrap 95% CI)
