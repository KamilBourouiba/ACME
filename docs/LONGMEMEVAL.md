# LongMemEval — industry benchmark integration

ACME integrates the official [LongMemEval](https://github.com/xiaowu0162/LongMemEval) benchmark (ICLR 2025) for external validation alongside MemoryBench v3.1.

## What we evaluate

| Setting | Dataset | Why |
|---------|---------|-----|
| **Oracle** (default) | `longmemeval_oracle.json` | Evidence sessions only — reproducible, lower API cost |
| Full history | `longmemeval_s.json` | ~115k tokens/question — optional, expensive |

**Scoring:** official LongMemEval yes/no LLM judge prompts (`evaluate_qa.py`), same as the paper.

**Systems compared:** ACME, RAG baseline, MemGPT baseline (same minimal runners as MemoryBench).

## Quick start

```bash
# 1. Download official oracle dataset (500 questions)
bash scripts/download_longmemeval.sh

# 2. Full comparison (requires LLM for judge + reasoning)
python scripts/run_longmemeval.py --systems acme,rag,memgpt

# 3. Knowledge-update subset only (78 questions in oracle set)
python scripts/run_longmemeval.py --types knowledge-update --systems acme,rag,memgpt

# 4. CI / offline smoke test (deterministic judge, fixture only)
python scripts/run_longmemeval.py --no-llm-judge --limit 7
```

Results are written to `benchmark-results/longmemeval-latest.json`.

## Fixture (committed)

`data/longmemeval/fixture_oracle_sample.json` — 7 questions covering all LongMemEval types + abstention. Used by `tests/test_longmemeval.py` without downloading the full dataset.

## Interpreting results

LongMemEval measures **QA accuracy over chat history** (retrieval + reading). MemoryBench measures **belief lifecycle, feedback, and CRS** — complementary, not interchangeable.

| Benchmark | Primary claim |
|-----------|----------------|
| LongMemEval | Competitive on industry-standard long-term memory QA |
| MemoryBench v3.1 | Leads on feedback correction and belief quality |

Published reference (LongMemEval paper, GPT-4o family): commercial assistants and long-context models show **30–60%** drops vs oracle on sustained memory. Use oracle subset scores for apples-to-apples adapter comparisons.

### Production results — full oracle 500 Q (v5 hybrid, canonical)

| System | Overall | KU | Multi-session | Temporal | Preference | Abstention |
|--------|---------|-----|---------------|----------|------------|------------|
| **ACME** | **0.876** | **0.944** | 0.793 | **0.803** | 0.900 | **0.833** |
| MemGPT | 0.786 | 0.861 | 0.793 | 0.630 | 0.600 | 0.600 |
| RAG | 0.776 | 0.875 | 0.793 | 0.622 | 0.467 | 0.600 |

Job `45623ca0`, image `acme-api:longmemeval-v5-hybrid`, GPT-4.1, 500 questions, ~6.2 h.  
Reproduce: `LONGMEMEVAL_TYPES=all bash scripts/run_longmemeval_prod.sh`

### Production results — knowledge-update only (v3, superseded for routing)

| System | Overall | KU | Abstention |
|--------|---------|-----|------------|
| **ACME** (transcript-first) | **0.897** | **0.931** | 0.500 |
| MemGPT | 0.872 | 0.903 | 0.500 |
| RAG | 0.859 | 0.875 | 0.667 |

Job `705eb2ff`, image `acme-api:longmemeval-transcript`, GPT-4.1, 78 questions, official judge.  
Reproduce: `bash scripts/run_longmemeval_prod.sh` → `benchmark-results/longmemeval-latest.json`.

ACME **transcript-first** path (`retrieve_longmemeval_episodes` + newest-first `build_transcript_memory_context` + `ollama.reason`) replaces graph-only query for LongMemEval; beliefs remain secondary context and KU demotion runs on ingest.

**v4 type routing (June 2026):** `longmemeval_answer_mode()` selects strategy per question type:
- `knowledge_update` — newest-first transcripts (KU)
- `multi_session` — vector-ranked + aggregate-all-sessions prompt
- `temporal` — chronological + date arithmetic prompt
- `abstention` (`*_abs`) — refuse when entity/topic not in context
- `preference` — cite user-stated preferences, not generic advice

## Architecture

```
longmemeval_oracle.json
        │
        ▼
  load_longmemeval_dataset()
        │
   ┌────┴────┬──────────┐
   ▼         ▼          ▼
 ACME      RAG       MemGPT
 ingest    ingest     ingest
   │         │          │
   └────┬────┴──────────┘
        ▼
  official LLM judge (yes/no)
        ▼
  accuracy + per question_type breakdown
```

Module: `acme/evaluation/longmemeval.py`

## Paper / reporting

Report LongMemEval **separately** from MemoryBench overall scores. Suggested table columns:

- Overall accuracy (oracle)
- `knowledge-update` accuracy
- `multi-session` accuracy
- MemoryBench overall (internal)

## References

- Wu et al., *LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory*, arXiv:2410.10813, 2024.
- Dataset: https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned
