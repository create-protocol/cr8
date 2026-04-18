# DePIN Cost Benchmark — Akash / io.net / Nosana vs Centralized Baselines

**Closes:** `create-protocol/cr8#2`
**Date:** 2026-04-18
**Analyst:** kcolbchain (gh: `abhicris`)
**Status:** Draft — **all USD figures marked `(unverified)` or `(estimated)` until a human operator runs the jobs and pins marketplace screenshots.**
**Scope:** SDXL image generation, Llama 3.1 70B inference, LoRA fine-tune on SDXL — across Akash, io.net, Nosana, and the centralized reference set (Replicate, Modal, RunPod, Lambda Labs).

> **Read this first.** Every cell in the pricing tables below is a paper benchmark.
> No jobs have been run against the three DePIN marketplaces yet. Numbers are
> pulled from public listings as of 2026-04-18 where available, and estimated
> from the prior 6 months of publicly-observed price bands where a provider
> does not publish a fixed rate. Mark the table as `DRAFT — NEEDS HUMAN
> VERIFICATION BEFORE PUBLIC CITATION`. The verification plan is §9.

---

## 1. Methodology

### 1.1 Workloads

| Workload | Definition | Output unit | Typical hardware tier |
|---|---|---|---|
| **W1 — SDXL inference** | SDXL 1.0 base, 1024×1024, 30 DPMSolver steps, fp16, batch sizes {1, 8} | USD / image | Single consumer or datacenter GPU: 4090 / 3090 / L40S / A100-80GB |
| **W2 — Llama 3.1 70B inference** | Llama-3.1-70B-Instruct, fp16 weights (~140GB) or AWQ-Int4 (~40GB), 1000-token completion, batch of 10 prompts @ 512 input tokens | USD / 1K output tokens | 2×A100-80GB or 1×H100-80GB (fp16); 1×L40S or 1×A100-80GB (AWQ-Int4) |
| **W3 — LoRA fine-tune** | LoRA (rank=16) on a 13B base model, 10K-sample dataset, 3 epochs, AdamW, fp16, batch 4 + grad accum 8 | USD / training run | 1×A100-80GB or 1×H100-80GB |

The cr8 issue #2 scope names SDXL + Llama-70B + "LoRA fine-tune on SDXL"; we expand the LoRA workload to a 13B text LoRA because text-LoRA pricing is the more common production ask and the SDXL LoRA (200-step, 500 images) costs ≈ 15 min × GPU hourly rate, which is trivial to tack on at the end.

### 1.2 Measurement window

- **Pricing snapshot date:** 2026-04-18 (all `(source: URL, observed: YYYY-MM-DD)` cells are observed on this day).
- **Wall-clock measurement:** N/A — no live jobs run yet. §9 defines how to close this gap.
- **Price source rule:** if a provider's own marketplace page quotes a USD/hour headline, that is the source. If not (Akash is a reverse auction; quotes fluctuate per lease), we use the median of leases observed on `cloudmos.io` or `akashlytics.com` over the prior 7 days. Mark such cells `(auction median, observed: 2026-04-18)`.

### 1.3 In-scope / out-of-scope cost components

**In-scope:**
- GPU compute USD/hour (on-demand rate).
- Container startup overhead (added as 30 s for DePIN, 5 s for hyperscalers; cold-start is a reliability factor, see §6).
- Model weight storage per run if the provider bills it as a separate line (Replicate's `private-model` tier, Modal's volume storage).

**Out-of-scope (flagged explicitly, not priced here):**
- Ingress/egress bandwidth. Most providers bundle or do not bill it at small scale; at >10GB-per-job scale it matters and would need its own pass.
- Persistent storage for user-supplied datasets (the 10K-sample LoRA set is ~2GB; free on every provider at this scale).
- Spot/preemptible pricing. All numbers here are on-demand. DePIN has no formal spot tier; the closest analogue is the auction median (already our Akash number).
- Multi-tenant orchestration / Kubernetes overhead.
- Protocol take rates, which is the point of the exercise — see §7.

### 1.4 Trust/SLA adjustment

DePIN providers have no enforceable SLA. We apply a **trust discount** when comparing to centralized: the DePIN headline price must be **≥ X% cheaper** for a rational operator to switch, where X is a function of workload criticality. §6 formalizes this.

---

## 2. GPU Hourly Price Table (USD / GPU-hour, on-demand)

All numbers are per-GPU, per-hour, USD. `unlisted, quote-based` means the marketplace does not publish a headline rate; a buyer must submit a lease/quote request. Dash `—` means the provider does not offer that tier at all in April 2026 to our knowledge.

| GPU tier | Akash | io.net | Nosana | Replicate (hourly-equivalent) | Modal | RunPod (Secure Cloud) | Lambda Labs |
|---|---|---|---|---|---|---|---|
| **RTX 3090 (24GB)** | $0.18 (auction median, unverified) | $0.22 (source: [io.net/explorer/hardware](https://io.net/explorer/hardware), observed: 2026-04-18, unverified) | $0.19 (estimated, unverified) | — | — | $0.22 (source: [runpod.io/gpu-cloud](https://runpod.io/gpu-cloud), unverified) | — |
| **RTX 4090 (24GB)** | $0.32 (auction median, unverified) | $0.39 (unverified) | $0.34 (unverified) | — | — | $0.44 (source: [runpod.io/gpu-cloud](https://runpod.io/gpu-cloud), unverified) | — |
| **L40S (48GB)** | $0.60 (auction median, unverified) | $0.79 (unverified) | unlisted, quote-based | — | $1.95 (source: [modal.com/pricing](https://modal.com/pricing), unverified) | $0.99 (unverified) | $1.40 (unverified) |
| **A100-80GB** | $1.10 (auction median, unverified) | $1.49 (unverified) | $1.35 (estimated, unverified) | — (bundled per-call) | $3.40 (source: [modal.com/pricing](https://modal.com/pricing), unverified) | $1.89 (unverified) | $1.79 (source: [lambdalabs.com/service/gpu-cloud](https://lambdalabs.com/service/gpu-cloud), unverified) |
| **H100-80GB** | $2.10 (auction median, unverified) | $2.49 (source: [io.net/explorer/hardware](https://io.net/explorer/hardware), observed: 2026-04-18, unverified) | unlisted, quote-based | — (bundled per-call) | $5.10 (source: [modal.com/pricing](https://modal.com/pricing), unverified) | $2.69 (unverified) | $2.99 (source: [lambdalabs.com/service/gpu-cloud](https://lambdalabs.com/service/gpu-cloud), unverified) |

**Observations about this table:**
1. **DePIN is cheaper at the GPU-hour line** for every consumer-tier row and most datacenter rows. The gap widens at A100/H100.
2. **Replicate does not publish a per-GPU-hour rate** — it meters per-second per-model-class. We back out an effective rate in §4.1.
3. **Nosana skews SDXL-workload-first.** Their H100/L40S inventory is thin; most listings are 4090/A100.
4. **Modal's base rate is 2-3× Akash** but includes container orchestration, auto-scaling, free GPU-idle bursts, and real SLA. Not apples-to-apples — see §5.

---

## 3. Workload Cost Models

Arithmetic for the cost formulas. Rates come from §2; throughput numbers are the working estimates most commonly reported in 2025-2026 public benchmarks and are flagged as such.

### 3.1 W1 — SDXL inference, 1024×1024, 30 steps

**Throughput baseline** (images/sec on common GPUs, 30-step DPMSolver, fp16; `(public benchmark, estimated, unverified)`):

| GPU | img/sec @ batch 1 | img/sec @ batch 8 |
|---|---|---|
| 4090 | 0.55 | 2.4 |
| L40S | 0.40 | 2.0 |
| A100-80GB | 0.50 | 2.6 |
| H100-80GB | 1.20 | 6.0 |

**Cost per image = GPU$/hr ÷ (img/sec × 3600)**

| Provider / GPU | batch 1 ($/img) | batch 8 ($/img) |
|---|---|---|
| Akash / 4090 @ $0.32 | $0.000162 | $0.0000370 |
| io.net / 4090 @ $0.39 | $0.000197 | $0.0000451 |
| Nosana / 4090 @ $0.34 | $0.000172 | $0.0000393 |
| RunPod / 4090 @ $0.44 | $0.000222 | $0.0000509 |
| Modal / L40S @ $1.95 | $0.001354 | $0.000271 |
| Akash / A100-80GB @ $1.10 | $0.000611 | $0.000117 |
| Akash / H100-80GB @ $2.10 | $0.000486 | $0.0000972 |

**Replicate equivalent (SDXL endpoint):** Replicate publishes `~$0.0025 per image` on the `stability-ai/sdxl` endpoint at default settings (source: [replicate.com/stability-ai/sdxl](https://replicate.com/stability-ai/sdxl), unverified, observed: 2026-04-18). That is **15–60× the batch-1 cost on DePIN 4090** and **~70× the batch-8 cost**, **before** adding trust discount.

**Verdict (W1):** DePIN wins decisively on naked cost. Even a 10× trust discount keeps DePIN ahead.

### 3.2 W2 — Llama 3.1 70B inference, 1000-token completion, batch 10 @ 512 input

**Throughput baseline** (output tokens/sec @ batch 10, 1000-token completion; `(public benchmark, estimated, unverified)`):

| Config | tokens/sec (aggregate) |
|---|---|
| 2×A100-80GB fp16, vLLM | 280 |
| 1×H100-80GB fp16, vLLM | 260 |
| 1×A100-80GB AWQ-Int4, vLLM | 180 |
| 1×L40S AWQ-Int4, vLLM | 95 |

**Cost per 1K output tokens = (GPU$/hr × N_GPUs) ÷ (tok/sec × 3.6)**

| Provider / Config | $/1K tokens |
|---|---|
| Akash / 2×A100-80GB fp16 @ $1.10 ea | $0.00218 |
| io.net / 2×A100-80GB fp16 @ $1.49 ea | $0.00296 |
| Akash / 1×H100-80GB fp16 @ $2.10 | $0.00224 |
| Akash / 1×A100-80GB AWQ-Int4 @ $1.10 | $0.00170 |
| Modal / 1×H100-80GB @ $5.10 | $0.00545 |
| RunPod / 1×A100-80GB AWQ-Int4 @ $1.89 | $0.00292 |

**Replicate / fal.ai equivalent (Llama-3.1-70B):** Replicate publishes roughly `$0.65 / 1M input tokens + $2.75 / 1M output tokens` on `meta/meta-llama-3.1-70b-instruct` (source: [replicate.com/meta/meta-llama-3.1-70b-instruct](https://replicate.com/meta/meta-llama-3.1-70b-instruct), unverified, observed: 2026-04-18). For a 1000-token completion with 512 input tokens per prompt, that's ≈ `(512 × 0.65 + 1000 × 2.75) / 1e6 = $0.00308 per request`, or **$0.00308 / 1K output tokens** as a unit-equivalent (since we normalize to the output token count).

**fal.ai:** does not publish a public Llama-70B rate at the time of snapshot; flagged as `unlisted, quote-based`.

**Groq / Together AI (managed-inference reference):** Together `llama-3.1-70b` is `$0.88 / 1M tokens blended` (source: [together.ai/pricing](https://together.ai/pricing), unverified, observed: 2026-04-18) → ~$0.00088 / 1K tokens. Groq is similarly low. **Managed-inference specialists beat both DePIN and Replicate on Llama-70B throughput pricing** because they batch and amortize across many tenants — a cost structure DePIN cannot match without an orchestration layer on top.

**Verdict (W2):** DePIN raw rate beats Replicate and Modal but **loses to Together AI / Groq** by ~2-3× on throughput-heavy inference. CR8's pitch cannot be "cheaper than Together for Llama-70B inference" — it can be "cheaper than a dedicated H100 on Modal/Replicate for bursty workloads where Together's per-token rate doesn't apply" (e.g., agent inference with custom weights or LoRAs).

### 3.3 W3 — LoRA fine-tune, 13B base, 10K samples, 3 epochs

**Runtime baseline** (hours to complete, `(estimated, unverified)` — depends heavily on sample length):

| GPU | hours |
|---|---|
| 1×A100-80GB | 5.0 |
| 1×H100-80GB | 2.8 |

**Cost per full fine-tune run:**

| Provider / GPU | Run cost (USD) |
|---|---|
| Akash / A100-80GB @ $1.10 | $5.50 |
| io.net / A100-80GB @ $1.49 | $7.45 |
| Nosana / A100-80GB @ $1.35 | $6.75 |
| RunPod / A100-80GB @ $1.89 | $9.45 |
| Lambda / A100-80GB @ $1.79 | $8.95 |
| Modal / A100-80GB @ $3.40 | $17.00 |
| Akash / H100-80GB @ $2.10 | $5.88 |
| Modal / H100-80GB @ $5.10 | $14.28 |

**Replicate equivalent (custom training):** Replicate prices training at `~$1.40 / minute on A100-40GB` for their SDXL-LoRA trainer (source: [replicate.com/blog/fine-tune-sdxl](https://replicate.com/blog/fine-tune-sdxl), unverified, observed: 2026-04-18). A 5-hour A100 training run ≈ `$420` — an order of magnitude above DePIN. Replicate's cost wedge is convenience (upload dataset, click train), not price.

**Verdict (W3):** DePIN wins 2-4× on naked cost. The friction is pipeline tooling — checkpointing, auto-restart on preemption, dataset staging — which today DePIN lacks. Operators willing to tolerate that friction capture the margin; operators who aren't will pay Replicate's markup.

### 3.4 Secondary — SDXL LoRA (200-step, 500 images) — the cr8 issue #2 version

Runtime: ~15 min on an A100-80GB (estimated, unverified).
Costs: Akash ≈ $0.28 / run; Replicate's `fine-tune-sdxl` product ≈ $3-5 / run.
Verdict: DePIN ~10× cheaper. Same story as W3 with smaller absolute numbers.

---

## 4. Centralized-Baseline Detail (apples-to-apples adjustments)

### 4.1 Backing out Replicate's implicit hourly rate

Replicate bills per second per SKU, not per GPU-hour. Their SDXL endpoint charges roughly `$0.0025/img` at batch 1 and reports ~2s/image on an A40. That implies `$0.0025 × 1800 = $4.50/hr effective on an A40`. Lambda's A40 on-demand rate is ~$0.79/hr — so **Replicate's margin over the underlying GPU is ~5-6×** for their hosted endpoints. The margin funds the convenience layer. Any CR8 marketplace strategy should assume Replicate will not price-cut to meet a DePIN floor; their moat is the API and the model catalog.

### 4.2 Modal

Modal does publish per-GPU-hour prices (rare among managed platforms), so the §2 row is direct. Modal's value above DePIN is (a) instant cold-start (they pre-warm containers), (b) automatic per-second billing down to 100ms granularity, (c) SDK-native Python. CR8 marketplace cannot dislodge Modal on dev-ergonomics within one year.

### 4.3 RunPod

RunPod has both "Secure Cloud" (datacenter) and "Community Cloud" (effectively a DePIN with an orchestration layer). Our §2 row uses Secure Cloud. **Community Cloud prices are within ~15-20% of Akash auction medians**, and RunPod ships the scheduler, container registry, and the team's web UI. RunPod Community is effectively the benchmark to beat: a DePIN with a working product wrapper.

### 4.4 Lambda Labs

Lambda is the closest "bare GPU, no orchestration" commodity supplier. Their prices set the floor for the centralized tier. DePIN is 30–60% cheaper than Lambda on the same tier.

---

## 5. Where DePIN Wins vs Where DePIN Loses

### Wins

1. **Consumer-tier batch-able image inference** (W1 batch 8). The headline $/img is so low relative to Replicate that even 50% reliability loss still wins on expected cost. **This is the single strongest CR8-marketplace wedge.**
2. **Training / fine-tuning runs that can tolerate checkpoint-and-resume semantics** (W3). 2-4× cheaper than Lambda/RunPod, ~10× cheaper than Replicate. The target persona is a developer who already scripts their training loop and can afford a 5% preemption rate.
3. **Custom-weight model inference** (e.g., a fine-tuned 13B running user-supplied LoRAs) where managed-inference providers don't have the model catalogued and the alternative is a dedicated H100 on Modal.

### Losses

1. **High-throughput shared-tenant inference** (W2 on any popular base model). Together AI / Groq win by ~2-3× on blended tokens/sec because they run a shared batched inference server. DePIN would need its own orchestration layer (a vLLM pool across tenant requests) to match, and at that point it is competing with the orchestration layer, not GPU-hour pricing.
2. **Enterprise / SLA-sensitive workloads.** DePIN cannot offer an SLA the enterprise will accept at any price. CR8 marketplace users in this segment will pay for Modal's 99.9% or AWS's 99.99% regardless of the headline GPU rate.
3. **Sub-second latency interactive inference.** Cold starts on DePIN are 30-90 s in the worst case. This is a non-starter for agentic loops that need a p95 of < 1 s.

### Trust/SLA discount (quantified)

For each workload class, the threshold at which a rational cost-minimizing operator should switch to DePIN (`(estimated, unverified)`):

| Workload class | Min DePIN discount vs centralized to justify switch |
|---|---|
| Batch image generation (reliability matters little) | ≥ 25% |
| Training runs (can resume from checkpoint) | ≥ 40% |
| Real-time inference (latency + reliability both matter) | ≥ 70% (and even then, rarely) |
| Enterprise / regulated inference | DePIN disqualified regardless of price |

Today's DePIN discount comfortably clears the first two and does not clear the third.

---

## 6. Reliability + Cold-Start — the Honest Column

Benchmarks that only quote $/GPU-hr lie about the user-experienced cost. DePIN has cold-start, node-churn, and lease-churn overheads that centralized providers don't.

**Rough estimates (unverified, would need a run to confirm):**

| Factor | Akash | io.net | Nosana | Modal | Replicate | RunPod (Secure) |
|---|---|---|---|---|---|---|
| P50 cold-start time | 45 s | 30 s | 60 s | 2 s | 3-8 s | 15 s |
| P95 cold-start time | 120 s | 90 s | 180 s | 6 s | 30 s | 45 s |
| Node preemption rate (daily) | 2-5% | 1-3% | 2-4% | 0% | 0% | <0.5% |
| Visible SLA guarantee | none | none | none | 99.9% (docs) | best-effort | 99.9% (docs) |
| Restart-on-preempt tooling | manual | some | none | native | native | native |

**For the compute-marketplace revenue thesis:** these numbers say CR8 should not position as a Replicate/Modal replacement for interactive inference. It can position as a **batch & training platform** where the cost win buys through the cold-start tax, and layer orchestration (auto-restart, checkpoint replication, provider-health routing) on top of the DePIN backend as the CR8 product.

---

## 7. Go/No-Go on CR8 Compute Marketplace at 2-3% Take Rate

### The arithmetic

Suppose CR8 takes 2.5% of GMV. A 2.5% take on a single workload:

| Workload | Representative job cost (DePIN, cheapest row) | CR8 take (2.5%) |
|---|---|---|
| W1 — 1000 SDXL images, batch 8, on Akash/4090 | $0.037 | $0.0009 |
| W2 — 1M Llama-70B tokens on Akash/2×A100 | $2.18 | $0.055 |
| W3 — one 13B LoRA run on Akash/A100 | $5.50 | $0.138 |

To generate **$10K/month in protocol revenue** from a 2.5% take, CR8 needs **$400K/month GMV**, which translates to roughly:
- **~10M SDXL images / month at batch 8** (W1), **or**
- **~180M Llama-70B tokens / month** (W2), **or**
- **~2900 LoRA fine-tunes / month** (W3), **or** some mix.

10M SDXL images/month is *plausible* — that is ~330K images/day, equivalent to ~3-5 mid-sized Civitai clones or a handful of AI-native consumer apps. 180M Llama-70B tokens is likewise plausible for a small agent-platform customer. The take-rate economics work **if** CR8 can source enough demand; the constraint is not the take rate, it is inventory × demand match.

### Inventory mix that makes the marketplace viable

Given §5 (where DePIN wins / loses) and §3 (per-workload price gaps), the recommended inventory priority:

1. **4090 / L40S on Akash + io.net** — W1 SDXL batch inference. Highest demand, best margin vs Replicate.
2. **A100-80GB on Akash + io.net** — W3 LoRA / fine-tune. Second-best margin, best narrative.
3. **H100-80GB on io.net (Akash auctions are thin at H100 in 2026-04)** — W2 Llama-70B inference for custom-weight use cases only. Do **not** market against Together/Groq on throughput.
4. **Nosana tier-2.** Nosana inventory is shallower than Akash or io.net for the tiers we need; treat it as a fail-over, not a primary.

### Recommendation: **Conditional GO.**

The economics support a 2-3% take rate **conditional on**:
- CR8 shipping the orchestration layer (auto-restart, checkpoint replication, provider-health routing) that DePIN raw lacks. Without this, the cold-start + preemption tax eats the price advantage in all but batch workloads.
- Positioning as a **batch & training** platform, not a real-time inference platform. Do not market against Together / Groq on Llama-70B throughput pricing; we will lose. Market against Replicate / Modal on $/image and $/fine-tune; we win.
- Clear "where we don't compete" copy — enterprise / low-latency / SLA-sensitive customers should be explicitly directed away. Selling a marketplace to a customer who will churn within a month because of cold-starts is worse than no sale.

If the team cannot commit to the orchestration layer in 2026 Q2-Q3, the answer is **conditional NO-GO**: without that layer, DePIN raw is too rough for anything except the most price-insensitive bulk-image workload, and that market is too small to sustain the 2.5% take economics.

---

## 8. Comparable Public References

For the operator reading this who wants to sanity-check the ranges:

- Akash Network pricing discovery: [console.akash.network](https://console.akash.network/), [akashlytics.com](https://akashlytics.com/) (unverified, observed: 2026-04-18).
- io.net explorer: [io.net/explorer/hardware](https://io.net/explorer/hardware) (unverified, observed: 2026-04-18).
- Nosana dashboard: [dashboard.nosana.io](https://dashboard.nosana.io/) (unverified, observed: 2026-04-18).
- Replicate model pricing: [replicate.com/pricing](https://replicate.com/pricing) (unverified).
- Modal pricing: [modal.com/pricing](https://modal.com/pricing) (unverified).
- RunPod pricing: [runpod.io/gpu-cloud](https://runpod.io/gpu-cloud) (unverified).
- Lambda Labs: [lambdalabs.com/service/gpu-cloud](https://lambdalabs.com/service/gpu-cloud) (unverified).
- Together AI pricing: [together.ai/pricing](https://together.ai/pricing) (unverified).

---

## 9. Uncertainty and Next Data to Gather

### Known gaps in this draft

1. **No live job runs on Akash / io.net / Nosana.** Every §3 cost cell combines a published rate with a public-benchmark throughput. Actual runs will differ — particularly the §6 cold-start and preemption columns, which are **educated estimates** and would flip some verdicts if reality diverges.
2. **Akash auction median is illustrative, not sampled.** A real benchmark should pull 7 days of `akashlytics.com` data and compute p50/p90 per GPU class.
3. **Nosana H100/L40S pricing is extrapolated from 4090 + A100 observations.** Their inventory skews SDXL-ready consumer GPUs; higher-end tiers may be quote-based in practice.
4. **Replicate / fal.ai per-model pricing changes frequently.** The $0.0025/img and $0.65/$2.75 per 1M tokens figures are our last-known rates; verify in-browser on the snapshot date before citing.
5. **Together AI / Groq are under-modeled.** The W2 "DePIN loses" verdict turns on a back-of-envelope $0.88/1M tokens; if that compresses further, the CR8 pitch for Llama-70B weakens.
6. **Trust/SLA discount thresholds in §5 are intuition, not surveyed.** A 20-buyer survey (operators currently on Replicate / Modal / RunPod) would put real numbers behind the "≥ 25% / ≥ 40% / ≥ 70%" lines.

### Verification plan — what to run and when

For this doc to move from DRAFT to citable:

| Gap | Data to gather | Owner | Effort |
|---|---|---|---|
| GPU-hour rate verification | Marketplace screenshots on Akash/io.net/Nosana/Replicate/Modal/RunPod/Lambda for each GPU tier, 2026-04-18 date-stamped, committed to `research/evidence/2026-04-18/` | human operator (1-2 hrs) | S |
| W1 real runs | Run 1000 images at batch 1 and batch 8 on Akash/4090, Akash/A100, io.net/4090, Modal/L40S, Replicate/SDXL endpoint. Record wall time + billed cost + failure rate. | human operator (4-6 hrs) | M |
| W2 real runs | Run Llama-3.1-70B with vLLM AWQ-Int4 on Akash/A100, io.net/H100, Modal/H100, Together AI. Same metrics. | human operator (4-6 hrs) | M |
| W3 real runs | Trigger one 13B LoRA training job on Akash/A100, RunPod/A100, Replicate fine-tune. Record end-to-end cost + time. | human operator (1 day) | L |
| Cold-start + preemption | Lease 10 times across a day on each DePIN provider, log cold-start P50/P95, log any preemption within 24 h. | human operator (1 day wall) | M |
| Trust/SLA survey | DM 10-20 operators currently on Replicate/Modal/RunPod. Ask what discount threshold would make them switch to a DePIN. | kcolbchain BD (1 week) | L |

**Budget to verify**: ~$150-300 in real compute costs (mostly the W3 fine-tune runs), 2-3 days of operator time.

### Numbers a human must verify before public citation

Before any of this is quoted in a CR8 investor deck, Arbitrum grant application, Messari briefing, or public blog post:

- The §2 GPU-hour table (all cells).
- The §3.1-§3.3 cost-per-unit cells (derived from §2 + throughput).
- The §5 DePIN-discount thresholds (intuition, not surveyed).
- The §6 cold-start P50/P95 numbers (estimated).
- The §7 go/no-go volume breakevens (direct arithmetic from above, but the 2.5% take and $10K/month targets should be set by the CR8 team, not inherited from this doc).

Until then, this document is an **internal decision-support artifact**, not a public research output.

---

*Document version 0.1 — 2026-04-18 — kcolbchain.*
