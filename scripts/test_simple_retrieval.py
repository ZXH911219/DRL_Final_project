"""Simple functional test: insert a synthetic slide with title into a temporary LanceDB
and run a text query to verify the hybrid retrieval returns it as a title-hit.
"""
from pathlib import Path
import shutil
import numpy as np
import uuid
import time

# Ensure project root is importable
import sys
sys.path.insert(0, str(Path.cwd()))

from src.storage.lancedb_manager import LanceDBManager, COLPALI_PATCHES, COLPALI_DIM
from src.agents.lakehouse_retrieval_agent import LakehouseRetrievalAgent, build_query_encoder_from_env
from src.schemas.query import QueryPayload
from src.schemas.enums import Modality

TMP_DB = Path("artifacts/test_lancedb_simple")
if TMP_DB.exists():
    shutil.rmtree(TMP_DB, ignore_errors=True)

lance = LanceDBManager(str(TMP_DB))

# create a normalized random colpali_multi (1024,128)
rng = np.random.default_rng(12345)
multi = rng.standard_normal((COLPALI_PATCHES, COLPALI_DIM), dtype=np.float32)
# normalize per patch
multi = multi / np.maximum(np.linalg.norm(multi, axis=1, keepdims=True), 1e-8)

slide_id = f"testdeck|p0001|{uuid.uuid4().hex[:8]}"
record = {
    "slide_id": slide_id,
    "deck_id": "testdeck",
    "page_index": 0,
    "source_path": "test_source",
    "colpali_multi": multi,  # LanceDB manager will normalize/convert
    "fts_text": "標題: SAC off-policy actor-critic architecture\n內文: Example slide about SAC off policy actor-critic architecture",
}

print("Adding synthetic slide record to temporary LanceDB...", TMP_DB)
start = time.time()
lance.add([record])
print("Added. Rows:", lance.count_rows(), "(took %.3fs)" % (time.time() - start))

# Build retrieval agent with stub encoder
agent = LakehouseRetrievalAgent(lance=lance, query_encoder=build_query_encoder_from_env(), evidence_top_n=3)

q = QueryPayload(request_id="test1", modality=Modality.TEXT, query_text="請找出SAC off policy 架構的投影片")
print("Running search for query:", q.query_text)
res = agent.search(q)

print("Candidates found:", len(res.candidates))
for c in res.candidates:
    print("- slide_id:", c.slide_id)
    mt = c.metadata.get("match_type")
    print("  match_type:", mt)
    print("  maxsim_score:", c.maxsim_score)
    print("  fts_text:", c.metadata.get("fts_text") or c.metadata.get("slide_caption") or "(none)")

# Cleanup
print("Test finished. Leaving temporary DB at:", TMP_DB)
