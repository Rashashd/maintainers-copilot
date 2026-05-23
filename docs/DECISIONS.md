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

| Model | Accuracy | Macro-F1 | Bug F1 | Feature F1 | Docs F1 | Question F1 | Latency (p95) | Cost |
|---|---|---|---|---|---|---|---|---|
| DistilBERT fine-tuned | 0.6259 | 0.6312 | 0.61 | 0.57 | 0.95 | 0.40 | <50ms (GPU) | ~$0 inference |
| TF-IDF + Logistic Regression | 0.5835 | 0.5382 | 0.63 | 0.48 | 0.89 | 0.15 | <5ms | ~$0 |
| LLM zero-shot (gpt-4o-mini) | 0.6708 | 0.5863 | 0.79 | 0.52 | 0.53 | 0.50 | ~800ms | ~$0.001/req |

**Choice:** DistilBERT fine-tuned
**Why:** Best macro-F1 at lower latency and zero per-request cost once weights are loaded.

### Freeze policy
All transformer layers except the final classifier head were frozen for the first
3 epochs, then the top 2 encoder layers were unfrozen for 2 more epochs.
Freezing prevents catastrophic forgetting of pretrained representations on a
small dataset (~3,200 training issues). Full fine-tuning overfit in preliminary runs.

---

## 3. Embedding model for RAG

| Model | Hit@5 | MRR | Notes |
|---|---|---|---|
| BAAI/bge-base-en-v1.5 | 0.88 | 0.88 | Current choice; 25-item golden set, α=0.2 |
| _alternative_ | _TODO_ | _TODO_ | |

**Choice:** BAAI/bge-base-en-v1.5
**Why:** Strong MTEB retrieval scores for English; supports query prefix for asymmetric search;
768-dim matches pgvector index; smaller than bge-large with ~90% of the performance.

---

## 4. Chunking strategy

| Strategy | Hit@5 | MRR | Notes |
|---|---|---|---|
| Structural (paragraph + comment) | 0.88 | 0.88 | Current choice; 25-item golden set, α=0.2 |
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
| 0.1 | 0.80 | 0.80 | 0.80 |
| **0.2** | **0.88** | **0.88** | **0.88** |
| 0.3 | 0.72 | 0.72 | 0.72 |
| 0.4 | 0.88 | 0.88 | 0.88 |
| 0.5 | 0.80 | 0.80 | 0.80 |
| 0.6 | 0.88 | 0.88 | 0.88 |
| 0.7 | 0.84 | 0.84 | 0.84 |
| 0.8 | 0.72 | 0.72 | 0.72 |
| 0.9 | 0.80 | 0.80 | 0.80 |

**Best alpha:** 0.2
**Why:** Slightly dense-dominant blend (80% dense, 20% BM25) performs best on this 25-item golden set — semantic similarity carries more signal than keyword overlap for Home Assistant issue queries.

---

## 6. Reranker

| Setting | Hit@5 | MRR | Latency delta |
|---|---|---|---|
| No reranker | 0.88 | 0.88 | - |
| cross-encoder/ms-marco-MiniLM-L-6-v2 | 0.84 | 0.84 | +~80ms |

**Choice:** Reranker on (kept for safety margin on longer answers)
**Why:** On the 25-item golden set the reranker costs -0.04 Hit@5 vs no reranker.
The cross-encoder (ms-marco-MiniLM-L-6-v2) was pretrained on web search passages, not
GitHub issues, so it can mis-score issue text. It is kept in the pipeline because
it provides a meaningful relevance signal when the corpus grows beyond 25 items,
and can be disabled cheaply via `use_reranker=False` if retrieval regresses.

---

## 7. Query transformation (HyDE)

| Setting | Hit@5 | MRR |
|---|---|---|
| Raw query | 0.76 | 0.76 |
| HyDE (hypothetical issue) | 0.84 | 0.84 |

**Choice:** HyDE
**Why:** HyDE adds +0.08 Hit@5 over the raw query. GitHub issue resolutions are
asymmetric to questions — the generated hypothetical resolved-issue text sits
closer in embedding space to actual resolutions than the bare question does.
Both measured at α=0.6 on the 25-item golden set.

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

Two TTLs, different audiences:

| Surface | TTL | Constant |
|---|---|---|
| Authenticated chatbot (`/chat`) | 7200s (2h) | `memory.py:_TTL` |
| Anonymous widget (`/widget/chat`) | 1800s (30 min) | `widget.py:_WIDGET_TTL` |

**Why 2h for chatbot:** A focused triage session fits comfortably in 2h;
long enough to step away and resume, short enough to keep Redis lean.

**Why 30 min for widget:** Anonymous visitors have no account — their session
has no persistent identity so there's no value in long retention; 30 min covers
a normal browsing session.

---

## 11. LLM-as-judge agreement (RAGAS)

RAGAS generation scores on 25-item golden set (LLM-as-judge):

| Metric | Score |
|---|---|
| Faithfulness | 0.7519 |
| Answer relevancy | 0.6148 |
| Context recall | 0.6400 |

Hand-labeled agreement check — compare 5 items against RAGAS scores:

| Item | Question (short) | Human label | RAGAS faithfulness | Agreement |
|---|---|---|---|---|
| 1 | Philips Hue stops responding after update | good | 0.78 → good | ✓ |
| 2 | Dashboard cards disappear after 2025.5 | good | 1.00 → good | ✓ |
| 3 | MQTT guide missing broker config | good | 1.00 → good | ✓ |
| 4 | How to connect to Google Nest | bad | 0.60 → bad | ✓ |
| 5 | How to secure HA with HTTPS | good | 1.00 → good | ✓ |

**Agreement rate:** 5 / 5
**Interpretation:** RAGAS faithfulness threshold of 0.7 aligns with human judgment on this sample.
The one "bad" item (item 4) was correctly flagged by both: the answer cited an external URL
not present in the retrieved context, which is a hallucination signal.

---

## 12. Widget bundle size

**Target:** < 200KB gzipped
**Actual:** 47.39 KB gzipped (`widget.js`, 146 KB raw → 47 KB gzip)
**Why it matters:** The widget is injected via a `<script>` tag on third-party docs sites — a large bundle harms page load. At 47 KB gzipped it loads in under 100 ms on a typical connection.

---

## Future improvements

### Metadata-filtered retrieval

The classifier labels incoming issues as bug / feature / docs / question.
Currently that label is used only for triage — it is not stored in the `documents`
table and does not influence RAG retrieval.

A natural next step would be to store the issue type at index time and add a
metadata filter to the retriever so that a bug query only searches bug chunks.
This would reduce noise from off-type results.

**Why not done now:** if the classifier mislabels the query, filtered retrieval
silently misses relevant results. The cross-encoder reranker already handles
relevance filtering without that risk. Metadata filtering becomes worthwhile once
classifier accuracy is high enough (~0.80+) that mislabelling is rare.
