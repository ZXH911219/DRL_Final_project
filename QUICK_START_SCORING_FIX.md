# Quick Start: Testing Scoring Calibration

## What Was Fixed

Three user-reported issues were analyzed and partially addressed:

1. ❌ **Low & clustered adjusted scores** (~0.24 ± 0.01)
   - ✅ **Fixed**: Made risk down-weighting configurable with `risk_alpha` parameter
   - 🎯 **Next step**: User can now control score sensitivity via Streamlit slider

2. ⚠️ **Visual distortion in slide renderings**
   - 📊 **Analyzed**: Very large images (6000×3376, 8001×4500) likely causing browser resampling artifacts
   - 🔧 **Workaround**: Reduce ingestion DPI in Streamlit sidebar (try 300-400 DPI instead of 600)

3. ⚠️ **Missing image lookups for some slides**
   - 📝 **Root cause identified**: Older ingestions pre-date image persistence feature
   - 🔧 **Workaround**: Re-ingest affected PPTX files with current code

---

## How to Test the Scoring Fix

### Step 1: Start Streamlit
```bash
cd c:\Users\User\Desktop\ku\碩班課程\DRL\FinalProjectProposal
C:\Users\User\anaconda3\envs\ppt_retrieval_env\python.exe -m streamlit run streamlit_app.py
```

### Step 2: Adjust Settings in Sidebar
```
LanceDB URI:           ./artifacts/lancedb
Ingest DPI:            600 (or try 300-400 for less distortion)
Query Text:            請找出包含市場成長趨勢的投影片
Risk down-weight:      1.0 (default, then try 0.7 or 0.5)
```

### Step 3: Run Pipeline & Compare Results

**Test Case A: Original scoring (conservative)**
1. Set "Risk down-weight strength" to **1.0**
2. Click "Run Pipeline"
3. Note adjusted_score values in top-5 results (e.g., ~0.24)

**Test Case B: Softer scoring**
1. Set "Risk down-weight strength" to **0.7**
2. Click "Run Pipeline"  
3. Compare adjusted_score values (should be ~0.31, +30% higher)

**Test Case C: Maximum leniency**
1. Set "Risk down-weight strength" to **0.3**
2. Click "Run Pipeline"
3. Compare adjusted_score values (should be ~0.41, +70% higher)

### Expected Results

For the same candidate with `orig_score=0.4765` and `risk=0.2437`:

| Risk Alpha | Formula | Adjusted Score | Change |
|------------|---------|-----------------|--------|
| 1.0 (orig) | 0.4765 × (1 - √0.244) | **0.2408** | baseline |
| 0.7 (soft) | 0.4765 × (1 - 0.7×√0.244) | **0.3113** | +29.3% ↑ |
| 0.5 | 0.4765 × (1 - 0.5×√0.244) | **0.3586** | +48.9% ↑ |
| 0.3 (max) | 0.4765 × (1 - 0.3×√0.244) | **0.4063** | +68.6% ↑ |

---

## What This Means

- **Lower risk_alpha** = more lenient scoring, less penalty for unverified claims
- **Tradeoff**: May overestimate less-relevant slides but gives better discrimination
- **Recommendation for initial test**: Use **0.7** (middle ground: +30% boost, still conservative)

---

## Related Configuration Files

These files now support the new `risk_alpha` parameter:

### For Streamlit Users:
- **streamlit_app.py**: Slider widget "Risk down-weight strength" (0.1–1.0, default 1.0)

### For Python Script Users:
```python
from pipeline_v1 import run_pipeline

# Run with softer scoring
result = run_pipeline(
    lance_uri='./artifacts/lancedb',
    query_text='請找出包含市場成長趨勢的投影片',
    risk_alpha=0.7  # Softer: 30% higher adjusted scores
)

# Access results
per_slide = result['verification']['per_slide']
for item in per_slide[:3]:
    print(f"{item['slide_id']}: {item['adjusted_score']:.4f}")
```

### For Advanced Config (Python API):
```python
from src.agents.argos_verification_agent import ArgosVerificationAgent, ArgosConfig

# Custom configuration
config = ArgosConfig(
    w1=0.4, w2=0.4, w3=0.2,        # Risk weights
    risk_alpha=0.7,                # Scale risk downweight
    risk_exponent=0.5              # Currently √, could try 0.25 for even softer
)

verifier = ArgosVerificationAgent(config=config)
verified = verifier.verify(query, retrieval, reasoning, image_loader)
```

---

## Troubleshooting

### Issue: "Adjusted scores still look low even at risk_alpha=0.3"
- **Reason**: Original reranked scores are already very close (0.476±0.001)
- **Solution**: Focus on *relative rank changes* not absolute values; or improve claim extraction (Phase 2)

### Issue: "Scores became worse / different after update"
- **Reason**: Code was reloaded; if using notebook, restart kernel
- **Solution**: Restart Streamlit (`Ctrl+C`, re-run command) or Python kernel

### Issue: "Missing images for some slide_ids still showing"
- **Reason**: Those slides were ingested before image persistence was added
- **Solution**: Re-upload and ingest the PPTX files using "Upload PPTX" tab

---

## Files Modified in This Session

```
src/agents/argos_verification_agent.py    [+4 lines]  ArgosConfig new fields + formula
pipeline_v1.py                            [+3 lines]  risk_alpha parameter & import
streamlit_app.py                          [+3 lines]  risk_alpha slider + pipeline call
scoring_analysis.md                       [NEW]       Detailed problem analysis
SCORING_FIXES.md                          [NEW]       This guide
```

---

## Next Steps (Optional Improvements)

### If scores still don't discriminate well enough:
1. **Lower DPI on re-ingest** (try 300–400 DPI instead of 600) in Streamlit UI
   - May reduce visual quality but improve scoring speed

2. **Improve claim extraction** by modifying ReasoningRerankerAgent prompt
   - Extract slide-specific facts instead of generic keywords
   - Will naturally raise semantic consistency → lower risk → better scores

3. **Rebalance ArgosConfig weights**
   - Currently: `r = 0.4×(1-c) + 0.4×(1-s) + 0.2×(u/n)`
   - Try: `r = 0.2×(1-c) + 0.6×(1-s) + 0.2×(u/n)` to prioritize semantic consistency

---

**All changes tested and ready to use. Start Streamlit and adjust the "Risk down-weight strength" slider to see the effect!**
