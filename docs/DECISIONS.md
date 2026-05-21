# DECISIONS.md

Every architectural and model choice is backed by a measurement on the golden sets.
Fill in numbers as evals are run. All results are on the 25-item golden sets unless
noted otherwise.

---

## 1. Open-source repo for the dataset

**Choice:** home-assistant/core + home-assistant/home-assistant.io
**Why:** Large volume of closed, labeled issues; labels map cleanly to bug/feature/docs/question;
public docs corpus available for RAG; real-world maintainer triage problem.

---

## 2. Classifier deployment

| Model | Accuracy | Macro-F1 | Latency (p95) | Cost |
|---|---|---|---|---|
| DistilBERT fine-tuned | 0.63 | 0.63 | <50ms (GPU) | ~$0 inference |
| TF-IDF + Logistic Regression | _TODO_ | _TODO_ | <5ms | ~$0 |
| LLM zero-shot (gpt-4o-mini) | 0.59 | 0.59 | ~800ms | ~$0.001/req |

**Choice:** DistilBERT fine-tuned
**Why:** Best macro-F1 at low latency; once weights are loaded, inference is free.

### Freeze policy
_TODO: describe which layers were frozen and why._

---

## 3. Embedding model for RAG

| Model | Hit@5 | MRR | Notes |
|---|---|---|---|
| BAAI/bge-base-en-v1.5 | _TODO_ | _TODO_ | Current choice |
| _alternative_ | _TODO_ | _TODO_ | |

**Choice:** BAAI/bge-base-en-v1.5
**Why:** Strong MTEB retrieval scores for English; supports query prefix for asymmetric search;
768-dim matches pgvector index; smaller than bge-large with ~90% of the performance.

---

## 4. Chunking strategy

| Strategy | Hit@5 | MRR | Notes |
|---|---|---|---|
| Structural (paragraph + comment) | _TODO_ | _TODO_ | Current choice |
| Fixed-size 512 tokens, 50-token overlap | _TODO_ | _TODO_ | Baseline |

**Choice:** Structural chunking
**Why:** Issue body split at paragraph boundaries preserves semantic units;
each comment is a separate chunk (comments often contain the resolution);
prefix with issue title improves retrieval context.

---

## 5. Sparse/dense weighting (alpha sweep)

Alpha controls the RRF blend: 0 = pure dense, 1 = pure sparse.

| Alpha | Hit@5 | MRR | NDCG@5 |
|---|---|---|---|
| 0.1 | 0.92 | 0.92 | 0.92 |
| 0.2 | 0.80 | 0.80 | 0.80 |
| 0.3 | 0.84 | 0.84 | 0.84 |
| 0.4 | 0.88 | 0.88 | 0.88 |
| 0.5 | 0.84 | 0.84 | 0.84 |
| 0.6 | 0.96 | 0.96 | 0.96 |
| 0.7 | 0.88 | 0.88 | 0.88 |
| 0.8 | 0.84 | 0.84 | 0.84 |
| 0.9 | 0.80 | 0.80 | 0.80 |

**Best alpha:** 0.6
**Why:** Slightly sparse-dominant blend (60% BM25, 40% dense) performs best on this corpus — keyword matching is strong for Home Assistant issue titles which contain specific integration names and error messages.

---

## 6. Reranker

| Setting | Hit@5 | MRR | Latency delta |
|---|---|---|---|
| No reranker | _TODO_ | _TODO_ | - |
| cross-encoder/ms-marco-MiniLM-L-6-v2 | _TODO_ | _TODO_ | +~80ms |

**Choice:** Reranker on
**Why:** _TODO: fill in once numbers are available_

---

## 7. Query transformation (HyDE)

| Setting | Hit@5 | MRR |
|---|---|---|
| Raw query | _TODO_ | _TODO_ |
| HyDE (hypothetical issue) | _TODO_ | _TODO_ |

**Choice:** HyDE
**Why:** GitHub issue answers are asymmetric to questions - the generated
hypothetical resolved issue is closer in embedding space to real resolutions.
_TODO: confirm with numbers._

**Fallback:** If HyDE measures worse, try raw BGE embed_query first;
if still worse, add multi-vector hypothetical questions at index time.

---

## 8. Tracing backend

**Choice:** Langfuse
**Why:** Self-hostable in Docker, free tier, purpose-built for LLM apps,
strong Python SDK with drop-in OpenAI integration, good trace UI.

---

## 9. Long-term memory type

**Choice:** Episodic
**Why:** Easiest to demo (cross-conversation recall is concrete);
maps naturally to the audit-log requirement; implemented via pgvector
semantic search over past turns.

---

## 10. Redis TTL for short-term memory

**Choice:** 86400s (24 hours)
**Why:** Typical triage session is under an hour; 24h allows same-day
resumption without losing context; longer TTLs waste Redis memory.

---

## 11. LLM-as-judge agreement (RAGAS)

Hand-labeled 5 of 25 RAG golden items independently.

| Item | Human label | RAGAS judge | Agreement |
|---|---|---|---|
| 1 | _TODO_ | _TODO_ | |
| 2 | _TODO_ | _TODO_ | |
| 3 | _TODO_ | _TODO_ | |
| 4 | _TODO_ | _TODO_ | |
| 5 | _TODO_ | _TODO_ | |

**Agreement rate:** _TODO_ / 5
**Action if < 4/5:** _TODO_

---

## 12. Widget bundle size

**Target:** < 200KB gzipped
**Actual:** _TODO_ (fill in after `npm run build`)
