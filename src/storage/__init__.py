"""儲存層（LanceDB 等）。"""

from __future__ import annotations

from .lancedb_manager import (
    COLPALI_DIM,
    COLPALI_FLAT_LEN,
    COLPALI_PATCHES,
    CoarseSearchHit,
    LanceDBManager,
    SLIDE_TABLE_FIELD_NAMES,
    colpali_multi_to_numpy,
    colpali_multi_value_type,
    compute_colpali_agg_128,
    coarse_distance_to_similarity_score,
    numpy_multi_to_nested_list,
    slide_table_schema,
)

__all__ = [
    "COLPALI_DIM",
    "COLPALI_FLAT_LEN",
    "COLPALI_PATCHES",
    "CoarseSearchHit",
    "LanceDBManager",
    "SLIDE_TABLE_FIELD_NAMES",
    "colpali_multi_to_numpy",
    "colpali_multi_value_type",
    "compute_colpali_agg_128",
    "coarse_distance_to_similarity_score",
    "numpy_multi_to_nested_list",
    "slide_table_schema",
]
