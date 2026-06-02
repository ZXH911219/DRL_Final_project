"""
LanceDB Vector Database Management Module
Handle vector storage, indexing, and retrieval operations.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


class LanceDBManager:
    """
    Manages LanceDB connection pool and distributed indexing.
    Handles vector operations, indexing strategies, and query execution.
    """

    def __init__(
        self,
        db_path: str = "./data/vector_store/lancedb",
        mode: str = "local",
        auto_connect: bool = True,
    ):
        """
        Initialize LanceDB manager.

        Args:
            db_path: Path to LanceDB database directory
            mode: "local" or "remote"
            auto_connect: Auto-connect on initialization
        """
        self.db_path = Path(db_path)
        self.mode = mode
        self._db = None
        self._tables = {}

        # Create DB path
        self.db_path.mkdir(parents=True, exist_ok=True)

        if auto_connect:
            self.connect()

    def connect(self) -> bool:
        """
        Connect to LanceDB instance.

        Returns:
            True if connection successful
        """
        try:
            import lancedb

            if self.mode == "local":
                self._db = lancedb.connect(str(self.db_path))
            else:
                # TODO: Implement remote connection
                raise NotImplementedError("Remote mode not yet implemented")

            return True
        except ImportError:
            print("ERROR: lancedb not installed. Run: pip install lancedb")
            return False
        except Exception as e:
            print(f"ERROR connecting to LanceDB: {e}")
            return False

    def is_connected(self) -> bool:
        """Check if connected to database."""
        return self._db is not None

    def create_table(
        self,
        name: str,
        data: Optional[List[Dict[str, Any]]] = None,
        schema: Optional[Dict[str, Any]] = None,
        overwrite: bool = False,
    ) -> bool:
        """
        Create or get a table.

        Args:
            name: Table name
            data: Initial data (list of dicts)
            schema: Table schema (optional)
            overwrite: Overwrite if exists

        Returns:
            True if successful
        """
        if not self.is_connected():
            print("ERROR: Not connected to LanceDB")
            return False

        try:
            if overwrite and name in self._tables:
                del self._tables[name]

            if data:
                # Create from data
                df = pd.DataFrame(data)
                table = self._db.create_table(
                    name,
                    data=df,
                    mode="overwrite" if overwrite else "create",
                )
            else:
                # Create empty table
                table = self._db.create_table(name, mode="overwrite" if overwrite else "create")

            self._tables[name] = table
            return True

        except Exception as e:
            print(f"ERROR creating table '{name}': {e}")
            return False

    def add_vectors(
        self,
        table_name: str,
        vectors: np.ndarray,
        metadata: Optional[List[Dict[str, Any]]] = None,
        overwrite: bool = False,
    ) -> bool:
        """
        Add vectors to table.

        Args:
            table_name: Target table name
            vectors: Vector array (N x D)
            metadata: Metadata for each vector

        Returns:
            True if successful
        """
        if not self.is_connected():
            print("ERROR: Not connected to LanceDB")
            return False

        try:
            # Prepare data
            data = []
            for i, vec in enumerate(vectors):
                if hasattr(vec, "tolist"):
                    vector_value = vec.tolist()
                else:
                    vector_value = list(vec)
                record = {"vector": vector_value}
                if metadata and i < len(metadata):
                    record.update(metadata[i])
                data.append(record)

            # Get or create table
            if overwrite:
                self.create_table(table_name, data=data, overwrite=True)
                return True

            if table_name not in self._tables:
                try:
                    self._tables[table_name] = self._db.open_table(table_name)
                except Exception:
                    self.create_table(table_name, data=data)
                    return True

            if table_name in self._tables:
                self._tables[table_name].add(data)

            return True

        except Exception as e:
            print(f"ERROR adding vectors: {e}")
            return False

    def search(
        self,
        table_name: str,
        query_vector: np.ndarray,
        k: int = 10,
        where: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for nearest vectors.

        Args:
            table_name: Search table
            query_vector: Query vector (D,)
            k: Number of results
            where: Optional filter clause

        Returns:
            List of results with similarity scores
        """
        if not self.is_connected():
            print("ERROR: Not connected to LanceDB")
            return []

        try:
            if table_name not in self._tables:
                print(f"ERROR: Table '{table_name}' not found")
                return []

            table = self._tables[table_name]
            query_list = query_vector.tolist() if isinstance(query_vector, np.ndarray) else query_vector

            # Execute search
            results = table.search(query_list).limit(k)

            # Apply where clause if provided
            if where:
                results = results.where(where)

            return results.to_list()

        except Exception as e:
            print(f"ERROR searching table '{table_name}': {e}")
            return []

    def hybrid_search(
        self,
        table_name: str,
        query_vector: np.ndarray,
        query_text: Optional[str] = None,
        k: int = 10,
        alpha: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search combining vector and text similarity.

        Args:
            table_name: Search table
            query_vector: Query vector
            query_text: Query text (optional)
            k: Number of results
            alpha: Weight for vector vs text (0.0-1.0)

        Returns:
            List of hybrid search results
        """
        # For now, just do vector search
        # TODO: Implement proper hybrid search
        return self.search(table_name, query_vector, k)

    def delete_table(self, name: str) -> bool:
        """Delete a table."""
        try:
            if name in self._tables:
                del self._tables[name]
            self._db.drop_table(name)
            return True
        except Exception as e:
            print(f"ERROR deleting table '{name}': {e}")
            return False

    def list_tables(self) -> List[str]:
        """List all tables in database."""
        try:
            return self._db.table_names()
        except Exception as e:
            print(f"ERROR listing tables: {e}")
            return []

    def get_table(self, table_name: str):
        """Open a table by name."""
        if not self.is_connected():
            return None

        try:
            return self._db.open_table(table_name)
        except Exception as e:
            print(f"ERROR opening table '{table_name}': {e}")
            return None

    def search_text(self, table_name: str, query_text: str, k: int = 10) -> List[Dict[str, Any]]:
        """Simple keyword search over slide metadata and text content."""
        if not self.is_connected() or not query_text.strip():
            return []

        table = self.get_table(table_name)
        if table is None:
            return []

        try:
            df = table.to_pandas()
        except Exception as e:
            print(f"ERROR reading table '{table_name}': {e}")
            return []

        query_tokens = [token for token in query_text.lower().split() if token]
        results: List[Dict[str, Any]] = []

        for _, row in df.iterrows():
            haystack_parts = [
                str(row.get("slide_id", "")),
                str(row.get("title", "")),
                str(row.get("text_content", "")),
                str(row.get("metadata", "")),
            ]
            haystack = " ".join(haystack_parts).lower()
            score = sum(1 for token in query_tokens if token in haystack)

            if score > 0:
                row_dict = row.to_dict()
                row_dict["score"] = score / max(len(query_tokens), 1)
                row_dict["title"] = row.get("title", "")
                results.append(row_dict)

        results.sort(key=lambda item: item.get("score", 0), reverse=True)
        return results[:k]

    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """Get table information."""
        try:
            if table_name not in self._tables:
                print(f"ERROR: Table '{table_name}' not found")
                return {}

            table = self._tables[table_name]
            return {
                "name": table_name,
                "num_rows": len(table.to_pandas()),
                "schema": str(table.schema),
            }
        except Exception as e:
            print(f"ERROR getting table info: {e}")
            return {}

    def close(self) -> bool:
        """Close database connection."""
        try:
            self._db = None
            self._tables = {}
            return True
        except Exception as e:
            print(f"ERROR closing connection: {e}")
            return False

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Global manager instance
_lancedb_manager: Optional[LanceDBManager] = None


def get_lancedb_manager(
    db_path: str = "./data/vector_store/lancedb",
    mode: str = "local",
) -> LanceDBManager:
    """Get or create global LanceDB manager."""
    global _lancedb_manager
    if _lancedb_manager is None:
        _lancedb_manager = LanceDBManager(db_path, mode)
    return _lancedb_manager


def init_lancedb(db_path: str = "./data/vector_store/lancedb", mode: str = "local") -> bool:
    """Initialize LanceDB manager."""
    global _lancedb_manager
    _lancedb_manager = LanceDBManager(db_path, mode)
    return _lancedb_manager.is_connected()
