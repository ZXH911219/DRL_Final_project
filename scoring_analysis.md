# Scoring Analysis: Why adjusted_score is so low

## Current Scoring Results
```
Rank  original_score  adjusted_score  risk_score  Δ (%)
 1     0.4761         0.2376         0.2510     -50.1%
 2     0.4760         0.2377         0.2507     -50.1%
 3     0.4760         0.2377         0.2507     -50.1%
```

## Root Cause Analysis

### 1. Original Reranked Scores are Clustered (0.476)
- **Why**: Both IVF-PQ coarse retrieval + MaxSim fine reranking use **same underlying ColPali embeddings**
- **Result**: All top-k results have nearly identical scores (~0.476 ± 0.001)
- **Problem**: No discrimination between actual relevant and borderline candidates

### 2. Extracted Claims are Generic
Example claims from reranker inference:
- "市場成長" (market growth)
- "趨勢" (trend)
- "成長率" (growth rate)

These are **very generic** and match *almost every slide* in a business presentation equally well, resulting in:
- **Low semantic consistency** (s ≈ 0-0.1)
- **High unverified claims ratio** (u/n ≈ 0.75+)
- **Inflated risk score** r ≈ 0.25

### 3. Risk Down-Weighting Formula is Aggressive
Formula: `s_adj = s_orig × (1 - sqrt(r))`

For r = 0.25:
```
1 - sqrt(0.25) = 1 - 0.5 = 0.5
s_adj = 0.4761 × 0.5 = 0.238
```

**This cuts the score by 50%** even though risk is moderate (0.25).

---

## Solution Options

### Option A: Tune ReasoningReranker Prompting
**Goal**: Extract discriminative, slide-specific claims instead of generic keywords.

Changes:
- Modify system prompt to extract **structural elements** (titles, key numbers, unique concepts)
- Add instruction: "Only extract facts that distinguish this slide from others"
- Example better claims: "Q3 2024 sales: $5.2M", "Market share up 15% YoY"

**Pros**: Improves semantic consistency; naturally raises adjusted_score
**Cons**: Requires prompt engineering; may need domain knowledge

---

### Option B: Adjust Risk Weighting Function
**Goal**: Make down-weighting less aggressive.

Options:
1. **Increase exponent** (currently 0.5):
   - `s_adj = s_orig × (1 - r^0.25)` → less aggressive
   - For r=0.25: `1 - 0.25^0.25 ≈ 1 - 0.707 ≈ 0.293` → **62% × 0.476 ≈ 0.295**

2. **Scale down risk contribution** (new `risk_alpha` parameter):
   - `s_adj = s_orig × (1 - 0.5 × sqrt(r))`
   - For r=0.25: `1 - 0.5 × 0.5 = 1 - 0.25 = 0.75` → **75% × 0.476 ≈ 0.357**

3. **Shift risk scale** (clip minimum impact):
   - `s_adj = s_orig × (1 - max(0, sqrt(r) - 0.2))`
   - For r=0.25: `1 - max(0, 0.5 - 0.2) = 1 - 0.3 = 0.7` → **70% × 0.476 ≈ 0.333**

**Pros**: Immediate effect; doesn't require reingestion
**Cons**: Ignores root cause (generic claims); may mask real hallucinations

---

### Option C: Rebalance ArgosConfig Weights
**Goal**: Reduce contribution of unverified_claims to risk.

Current weights:
```
r = 0.4 × (1 - completeness) + 0.4 × (1 - semantic_consistency) + 0.2 × (unverified / total)
```

Change to (example):
```
r = 0.2 × (1 - completeness) + 0.6 × (1 - semantic_consistency) + 0.2 × (unverified / total)
```

**Result**: Generic unverified claims matter less; semantic consistency dominates.

**Pros**: Encourages reranker to extract better claims; less risk inflation from poor claims
**Cons**: Still doesn't fix generic claim extraction

---

## Recommendation

**Phase 1 (immediate)**: Apply Option B with **`risk_alpha = 0.7`** to give intermediate relief
- Reduces aggressive down-weighting
- Example: r=0.25 → adjusted now **0.333** instead of **0.238** (+40%)

**Phase 2 (production)**: Fix claim extraction (Option A)
- Modify reranker prompt to extract discriminative facts
- Run ingestion/reranking pipeline
- Monitor adjusted_score distribution

**Phase 3 (tuning)**: Once claims are better, re-calibrate ArgosConfig weights

---

## Implementation

To test Option B with `risk_alpha = 0.7`:

```python
from src.agents.argos_verification_agent import ArgosVerificationAgent, ArgosConfig

config = ArgosConfig(risk_alpha=0.7)
verifier = ArgosVerificationAgent(config=config)
verified = verifier.verify(query, retrieval, reasoning, slide_loader)
```

Current codebase already supports this via configurable `ArgosConfig`.
