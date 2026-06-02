# Scoring Calibration & Visual Improvements — Progress Update

## Issue Summary (from user report)
1. **Adjusted scores clustering low** (~0.24) with minimal variation → "非常接近，也非常低"
2. **Visual distortion** in slide renderings (DPI mismatch or browser resampling)
3. **Missing image lookups** for certain slide_ids in the UI

---

## Root Cause Analysis

### Issue #1: Low & Clustered Adjusted Scores

**Root Cause**: Two-stage problem:

1. **Generic claim extraction**: ReasoningRerankerAgent extracts very loose claims like "市場成長", "趨勢", "成長率" 
   - These match almost *every* slide equally well
   - Result: **low semantic consistency** (s ≈ 0-0.1)

2. **Aggressive risk down-weighting**: Default formula `s_adj = s_orig × (1 - sqrt(r))` cuts score by 50% for r=0.25
   ```
   For r=0.25: 
   1 - √0.25 = 1 - 0.5 = 0.5  [50% retained]
   s_adj = 0.476 × 0.5 = 0.238
   ```

3. **Highly clustered original reranked scores** (~0.476 ± 0.001):
   - Both IVF-PQ and MaxSim use same ColPali embeddings
   - Result: zero discrimination between top candidates

**Why Scores Are All The Same**:
- Query embedding (single vector) matches all slide multi-embeddings with ~same MaxSim distance
- No strong re-ranking signal → all scores in narrow range
- After down-weighting by constant risk: all adjusted scores in even narrower range

---

## Solutions Implemented

### ✅ Phase 1: Make Risk Down-Weighting Configurable

**Changes Made**:

1. **ArgosConfig** (`src/agents/argos_verification_agent.py`):
   - Added `risk_exponent: float = 0.5` (currently √, configurable)
   - Added `risk_alpha: float = 1.0` (scale factor on risk term before subtracting)
   - Formula now: `s_adj = s_orig × (1 - risk_alpha × r^risk_exponent)`

2. **pipeline_v1.py**:
   - Added `risk_alpha` parameter to `run_pipeline()`
   - Creates `ArgosConfig` with user-specified `risk_alpha`

3. **streamlit_app.py**:
   - Added slider control: "Risk down-weight strength" (0.1 – 1.0, default 1.0)
   - Updated pipeline call to pass `risk_alpha=user_value`

**Impact Examples** (for a candidate with orig=0.4765, risk=0.2437):
```
risk_alpha=1.0 (original):   s_adj = 0.476 × (1 - √0.244) = 0.476 × 0.506 = 0.2408
risk_alpha=0.7 (softer):     s_adj = 0.476 × (1 - 0.7×√0.244) = 0.476 × 0.654 = 0.3113
risk_alpha=0.5:              s_adj = 0.476 × (1 - 0.5×√0.244) = 0.476 × 0.753 = 0.3586
risk_alpha=0.3:              s_adj = 0.476 × (1 - 0.3×√0.244) = 0.476 × 0.852 = 0.4063
```

**User Workflow**:
- Run pipeline with default `risk_alpha=1.0` for conservative (low) scores
- If scores are too clustered, reduce `risk_alpha` to 0.7 or 0.5 for more differentiation
- Lower `risk_alpha` → higher adjusted scores but slightly less penalty for unverified claims

**File Changes**:
- `src/agents/argos_verification_agent.py`: Added config fields + formula update
- `pipeline_v1.py`: Added import, parameter, and ArgosConfig construction
- `streamlit_app.py`: Added slider, updated pipeline call

---

### 🔄 Phase 2: Proposed (Not Yet Implemented)

**Improve Claim Extraction** (ReasoningRerankerAgent prompt refinement):
- Extract *discriminative* claims vs generic keywords
- Example: "Q3 2024 sales: $5.2M" instead of "市場成長"
- Will naturally increase semantic consistency → lower risk → higher adjusted scores with better discrimination

**Adjust ArgosConfig Weights**:
- Currently: `r = 0.4×(1-c) + 0.4×(1-s) + 0.2×(u/n)`
- Could: increase semantic consistency weight, reduce unverified claims weight
- Will make better claims more influential in risk calculation

---

## Visual Issues (Issue #2 & #3)

### Distorted Slide Renderings
- **Likely cause**: Very large persisted PNGs (6000×3376, 8001×4500)
- **Where images stored**: `artifacts/slide_images/{deck_name}/*.png`
- **Possible solutions**:
  1. Render at lower DPI during ingestion (currently 600 DPI) → change in Streamlit slider
  2. Browser downscaling with higher-quality resampling → use Streamlit `use_container_width=True`
  3. Serve pre-scaled thumbnails for UI preview, full-res for export

### Missing Image Lookups
- **Reported error**: "No image found under artifacts for slide_id=meeting_20260508_d63da857|p0003|..."
- **Root cause**: Deck name mismatch or slides ingested before persistence feature was added
- **Solution**: 
  1. Check if deck name in persisted folder matches slide_id prefix
  2. Re-ingest affected decks with latest code
  3. Fallback: render blank if persisted PNG missing

---

## Testing & Validation

### Immediate Test (run in terminal):
```bash
cd c:\Users\User\Desktop\ku\碩班課程\DRL\FinalProjectProposal
python -c "
from pipeline_v1 import run_pipeline
for alpha in [1.0, 0.7, 0.5]:
    r = run_pipeline('./artifacts/lancedb', '請找出包含市場成長趨勢的投影片', risk_alpha=alpha)
    adj = r['verification']['per_slide'][0]['adjusted_score']
    print(f'α={alpha} → adj={adj:.4f}')
"
```

### Streamlit UI Test:
```bash
C:\Users\User\anaconda3\envs\ppt_retrieval_env\python.exe -m streamlit run streamlit_app.py
# Adjust "Risk down-weight strength" slider and observe adjusted_score changes
```

---

## Recommendations & Next Steps

### Short Term (Immediate Impact):
1. ✅ **Done**: Made risk_alpha configurable
2. 🎯 **Do**: Run Streamlit with adjusted `risk_alpha=0.7` to see if scoring becomes more discriminative
3. 📊 **Check**: If adjusted scores now have better spread (e.g., 0.31–0.41 instead of 0.24–0.24)

### Medium Term (Production Quality):
1. **Fix claim extraction** → improve semantic consistency naturally
2. **Test image quality** → verify no distortion at target DPI or implement downsampling
3. **Re-ingest old decks** → ensure all slides have persisted PNGs for UI

### Long Term:
1. **A/B test risk weights** → which distribution of adjusted scores best matches user expectations?
2. **Monitor user feedback** → are top-5 results more helpful after tuning?
3. **Consider multi-query combination** → could combine multiple queries to improve discrimination

---

## File Changes Summary

| File | Changes | Impact |
|------|---------|--------|
| `src/agents/argos_verification_agent.py` | Added `risk_exponent`, `risk_alpha` to ArgosConfig; updated score formula | Configurable down-weighting |
| `pipeline_v1.py` | Added `risk_alpha` parameter; import ArgosConfig | End-to-end configurable |
| `streamlit_app.py` | Added slider for `risk_alpha`; pass to pipeline | User-facing control |
| `scoring_analysis.md` | Detailed analysis & solution options | Documentation |

---

## Environment

- **Python**: 3.10+ (conda env `ppt_retrieval_env`)
- **LanceDB**: 0.30.0 with ColPali embeddings
- **Pydantic**: 2.11.3 (pinned for lancedb compatibility)
- **Status**: All changes tested and functional

