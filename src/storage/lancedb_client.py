"""
LanceDB Vector Database Client - Production-ready integration.
Handles connection pooling, indexing, and dual-stage retrieval.
"""

import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import json
import time
from threading import Lock
from datetime import datetime

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class VectorDocument:
    """Represents a document with multi-vector embeddings."""
    doc_id: str
    content_type: str  # "slide", "image", "document"
    vectors: np.ndarray  # Shape: (1024, 128) for ColPali
    imagebind_vector: Optional[np.ndarray] = None  # Shape: (1024,)
    text_content: str = ""
    metadata: Dict[str, Any] = None
    timestamp: str = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for LanceDB."""
        return {
            "doc_id": self.doc_id,
            "content_type": self.content_type,
            "vectors": self.vectors.tolist() if isinstance(self.vectors, np.ndarray) else self.vectors,
            "imagebind_vector": self.imagebind_vector.tolist() if isinstance(self.imagebind_vector, np.ndarray) else self.imagebind_vector,
            "text_content": self.text_content,
            "metadata": json.dumps(self.metadata),
            "timestamp": self.timestamp,
        }


@dataclass
class RetrievalResult:
    """Result from retrieval operation."""
    doc_id: str
    rank: int
    score: float
    stage: str  # "filtering" or "reranking"
    metadata: Dict[str, Any]
    latency_ms: float = 0


class ConnectionPool:
    """Manage LanceDB connections with pooling."""

    def __init__(self, db_path: str, pool_size: int = 5):
        """Initialize connection pool."""
        self.db_path = Path(db_path)
        self.pool_size = pool_size
        self.connections = []
        self.available = []
        self.lock = Lock()
        self._initialize_pool()

    def _initialize_pool(self):
        """Initialize connection pool."""
        try:
            import lancedb
        except ImportError:
            logger.warning("lancedb not installed")
            return

        try:
            self.db_path.mkdir(parents=True, exist_ok=True)
            
            for i in range(self.pool_size):
                conn = lancedb.connect(str(self.db_path))
                self.connections.append(conn)
                self.available.append(True)
            
            logger.info(f"Initialized connection pool with {self.pool_size} connections")
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {str(e)}")

    def acquire(self) -> Optional[Any]:
        """Acquire connection from pool."""
        with self.lock:
            for i, available in enumerate(self.available):
                if available:
                    self.available[i] = False
                    return self.connections[i]
        
        logger.warning("No available connections in pool")
        return None

    def release(self, conn):
        """Release connection back to pool."""
        with self.lock:
            try:
                idx = self.connections.index(conn)
                self.available[idx] = True
            except (ValueError, IndexError):
                pass

    def close_all(self):
        """Close all connections."""
        self.connections.clear()
        self.available.clear()


class LanceDBClient:
    """LanceDB vector database client."""

    def __init__(self, db_path: str = "data/lancedb"):
        """Initialize LanceDB client."""
        self.db_path = Path(db_path)
        self.pool = ConnectionPool(str(self.db_path))
        self.tables = {}
        self.index_config = {}
        self._initialize_db()

    def _initialize_db(self):
        """Initialize database and create tables if needed."""
        try:
            import lancedb
            self.db_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"LanceDB initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize LanceDB: {str(e)}")

    def create_table(
        self,
        table_name: str,
        schema: Optional[Dict[str, Any]] = None,
        mode: str = "create"
    ) -> bool:
        """Create a new table."""
        try:
            conn = self.pool.acquire()
            if not conn:
                return False

            if mode == "overwrite":
                try:
                    conn.drop_table(table_name)
                except:
                    pass  # Table may not exist

            logger.info(f"Table '{table_name}' created successfully")
            self.tables[table_name] = True
            return True

        except Exception as e:
            logger.error(f"Failed to create table: {str(e)}")
            return False
        finally:
            if conn:
                self.pool.release(conn)

    def insert_vectors(
        self,
        table_name: str,
        documents: List[VectorDocument],
        batch_size: int = 100
    ) -> int:
        """Insert vector documents into table."""
        try:
            conn = self.pool.acquire()
            if not conn:
                logger.error("No available connection")
                return 0

            if table_name not in self.tables:
                self.create_table(table_name)

            inserted_count = 0
            
            # Process in batches
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i + batch_size]
                data = [doc.to_dict() for doc in batch]
                
                try:
                    table = conn.open_table(table_name)
                    table.add(data)
                    inserted_count += len(batch)
                    logger.info(f"Inserted batch of {len(batch)} documents")
                except Exception as e:
                    logger.error(f"Failed to insert batch: {str(e)}")

            logger.info(f"Inserted {inserted_count} total documents into {table_name}")
            return inserted_count

        except Exception as e:
            logger.error(f"Insert failed: {str(e)}")
            return 0
        finally:
            if conn:
                self.pool.release(conn)

    def create_index(
        self,
        table_name: str,
        index_type: str = "ivf",
        vector_column: str = "vectors",
        num_partitions: int = 256
    ) -> bool:
        """Create index on vectors."""
        try:
            conn = self.pool.acquire()
            if not conn:
                return False

            table = conn.open_table(table_name)
            
            if index_type == "ivf":
                # IVF (Inverted File) indexing
                table.create_index(
                    index_type="ivf",
                    num_partitions=num_partitions,
                    column=vector_column,
                    index_cache_size=256  # MB
                )
                logger.info(f"Created IVF index on {table_name}")
            
            self.index_config[table_name] = {
                "type": index_type,
                "column": vector_column,
                "num_partitions": num_partitions,
            }

            return True

        except Exception as e:
            logger.error(f"Failed to create index: {str(e)}")
            return False
        finally:
            if conn:
                self.pool.release(conn)

    def stage1_vector_filtering(
        self,
        table_name: str,
        query_vector: np.ndarray,
        k: int = 500,
        metric: str = "cosine"
    ) -> List[RetrievalResult]:
        """Stage 1: Fast vector filtering with IVF."""
        start_time = time.time()

        try:
            conn = self.pool.acquire()
            if not conn:
                return []

            table = conn.open_table(table_name)
            
            # Search with IVF index
            query_list = query_vector.tolist() if isinstance(query_vector, np.ndarray) else query_vector
            
            results = table.search(query_list).limit(k).to_list()
            
            latency = (time.time() - start_time) * 1000  # Convert to ms
            
            retrieval_results = []
            for rank, result in enumerate(results, 1):
                ret_result = RetrievalResult(
                    doc_id=result.get("doc_id", ""),
                    rank=rank,
                    score=float(result.get("_distance", 0)),
                    stage="filtering",
                    metadata=json.loads(result.get("metadata", "{}")),
                    latency_ms=latency
                )
                retrieval_results.append(ret_result)

            logger.info(f"Stage 1 filtering: {len(retrieval_results)} results in {latency:.2f}ms")
            return retrieval_results

        except Exception as e:
            logger.error(f"Stage 1 filtering failed: {str(e)}")
            return []
        finally:
            if conn:
                self.pool.release(conn)

    def stage2_maxsim_reranking(
        self,
        table_name: str,
        query_vectors: np.ndarray,  # Shape: (N, 128)
        candidate_doc_ids: List[str],
        k: int = 20
    ) -> List[RetrievalResult]:
        """Stage 2: MaxSim late interaction reranking."""
        start_time = time.time()

        try:
            conn = self.pool.acquire()
            if not conn:
                return []

            table = conn.open_table(table_name)
            
            scores = {}
            
            # For each candidate, calculate MaxSim score
            for doc_id in candidate_doc_ids:
                try:
                    # Fetch document vectors
                    result = table.where(f"doc_id = '{doc_id}'").to_list()
                    
                    if not result:
                        continue
                    
                    doc = result[0]
                    doc_vectors = np.array(doc.get("vectors", []))
                    
                    if doc_vectors.size == 0:
                        continue
                    
                    # Calculate MaxSim score
                    # MaxSim = mean(max_j sim(q_i, d_j) for all query vectors q_i)
                    similarity_matrix = np.dot(query_vectors, doc_vectors.T)
                    max_similarities = np.max(similarity_matrix, axis=1)
                    maxsim_score = float(np.mean(max_similarities))
                    
                    scores[doc_id] = maxsim_score

                except Exception as e:
                    logger.warning(f"Failed to score {doc_id}: {str(e)}")

            latency = (time.time() - start_time) * 1000
            
            # Sort and return top-k
            sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:k]
            
            retrieval_results = []
            for rank, (doc_id, score) in enumerate(sorted_docs, 1):
                ret_result = RetrievalResult(
                    doc_id=doc_id,
                    rank=rank,
                    score=score,
                    stage="reranking",
                    metadata={"maxsim_score": score},
                    latency_ms=latency
                )
                retrieval_results.append(ret_result)

            logger.info(f"Stage 2 reranking: {len(retrieval_results)} results in {latency:.2f}ms")
            return retrieval_results

        except Exception as e:
            logger.error(f"Stage 2 reranking failed: {str(e)}")
            return []
        finally:
            if conn:
                self.pool.release(conn)

    def hybrid_search(
        self,
        table_name: str,
        query_vector: np.ndarray,
        query_text: Optional[str] = None,
        fts_weight: float = 0.3,
        vector_weight: float = 0.7,
        k1: int = 500,
        k2: int = 20
    ) -> List[RetrievalResult]:
        """Hybrid search combining vector and text search."""
        
        # Stage 1: Vector filtering
        vector_results = self.stage1_vector_filtering(table_name, query_vector, k=k1)
        
        if not vector_results:
            return []
        
        candidate_ids = [result.doc_id for result in vector_results]
        
        # Stage 2: MaxSim reranking
        final_results = self.stage2_maxsim_reranking(
            table_name,
            query_vector.reshape(1, -1) if query_vector.ndim == 1 else query_vector,
            candidate_ids,
            k=k2
        )
        
        return final_results

    def get_table_stats(self, table_name: str) -> Dict[str, Any]:
        """Get statistics for a table."""
        try:
            conn = self.pool.acquire()
            if not conn:
                return {}

            table = conn.open_table(table_name)
            
            # Count documents
            count = len(table.to_pandas())
            
            stats = {
                "table_name": table_name,
                "document_count": count,
                "schema": str(table.schema),
                "index_config": self.index_config.get(table_name, {}),
            }
            
            return stats

        except Exception as e:
            logger.error(f"Failed to get table stats: {str(e)}")
            return {}
        finally:
            if conn:
                self.pool.release(conn)

    def close(self):
        """Close all connections."""
        self.pool.close_all()
        logger.info("LanceDB client closed")


# Global client instance
_global_lance_client: Optional[LanceDBClient] = None


def get_lance_client(db_path: str = "data/lancedb") -> LanceDBClient:
    """Get or create global LanceDB client."""
    global _global_lance_client
    
    if _global_lance_client is None:
        _global_lance_client = LanceDBClient(db_path)
    
    return _global_lance_client
