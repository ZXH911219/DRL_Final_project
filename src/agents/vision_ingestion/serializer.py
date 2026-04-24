"""
Serialization for Vision-Ingestion-Agent
Serialize multi-vectors to Parquet and HDF5 formats for storage and retrieval.
"""

import h5py
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import json
import logging


logger = logging.getLogger(__name__)


class FeatureBundleSerializer:
    """Serialize visual feature bundles to efficient formats."""

    # Format type constants
    FORMAT_PARQUET = "parquet"
    FORMAT_HDF5 = "hdf5"

    def __init__(self, output_dir: str = "feature_bundles"):
        """Initialize serializer."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _prepare_parquet_data(
        feature_bundles: List[Dict[str, Any]],
    ) -> pa.Table:
        """
        Prepare feature bundles for Parquet serialization.

        Args:
            feature_bundles: List of feature bundle dicts

        Returns:
            PyArrow Table
        """
        data = {
            "slide_id": [],
            "page_index": [],
            "multi_vectors_shape": [],
            "imagebind_vector_shape": [],
            "patch_coordinates": [],
            "metadata": [],
            "quality_metrics": [],
            "timestamp": [],
        }

        for bundle in feature_bundles:
            data["slide_id"].append(bundle.get("slide_id"))
            data["page_index"].append(bundle.get("page_index"))
            data["multi_vectors_shape"].append(
                str(bundle.get("multi_vectors", np.array([])).shape)
            )
            data["imagebind_vector_shape"].append(
                str(bundle.get("imagebind_vector", np.array([])).shape)
            )
            data["patch_coordinates"].append(json.dumps(bundle.get("patch_coordinates", [])))
            data["metadata"].append(json.dumps(bundle.get("metadata", {})))
            data["quality_metrics"].append(json.dumps(bundle.get("quality_metrics", {})))
            data["timestamp"].append(bundle.get("timestamp", datetime.now().isoformat()))

        return pa.table(data)

    def serialize_to_parquet(
        self,
        feature_bundles: List[Dict[str, Any]],
        output_file: str,
        compression: str = "snappy",
    ) -> str:
        """
        Serialize feature bundles to Parquet format.

        Args:
            feature_bundles: List of feature bundle dicts
            output_file: Output file path
            compression: Compression type ('snappy', 'gzip', 'brotli', 'lz4', 'zstd')

        Returns:
            Path to saved file
        """
        output_path = self.output_dir / output_file
        logger.info(f"Serializing {len(feature_bundles)} bundles to Parquet: {output_path}")

        try:
            table = self._prepare_parquet_data(feature_bundles)
            pq.write_table(table, str(output_path), compression=compression)
            logger.info(f"Successfully saved to {output_path}")
            return str(output_path)

        except Exception as e:
            logger.error(f"Failed to serialize to Parquet: {str(e)}")
            raise

    def serialize_to_hdf5(
        self,
        feature_bundles: List[Dict[str, Any]],
        output_file: str,
        chunk_size: Optional[int] = None,
    ) -> str:
        """
        Serialize feature bundles to HDF5 format.

        Args:
            feature_bundles: List of feature bundle dicts
            output_file: Output file path
            chunk_size: Chunk size for HDF5 datasets

        Returns:
            Path to saved file
        """
        output_path = self.output_dir / output_file
        logger.info(f"Serializing {len(feature_bundles)} bundles to HDF5: {output_path}")

        try:
            with h5py.File(str(output_path), "w") as f:
                # Create metadata dataset (text information)
                metadata_group = f.create_group("metadata")

                for i, bundle in enumerate(feature_bundles):
                    slide_group = metadata_group.create_group(f"slide_{i}")
                    slide_group.attrs["slide_id"] = bundle.get("slide_id", "")
                    slide_group.attrs["page_index"] = bundle.get("page_index", -1)
                    slide_group.attrs["timestamp"] = bundle.get(
                        "timestamp", datetime.now().isoformat()
                    )

                # Create vectors dataset (numerical data)
                vectors_group = f.create_group("vectors")

                for i, bundle in enumerate(feature_bundles):
                    multi_vecs = bundle.get("multi_vectors", np.array([]))
                    imagebind_vec = bundle.get("imagebind_vector", np.array([]))

                    if multi_vecs.size > 0:
                        vectors_group.create_dataset(
                            f"multi_vectors_{i}",
                            data=multi_vecs,
                            compression="gzip",
                            chunks=True,
                        )

                    if imagebind_vec.size > 0:
                        vectors_group.create_dataset(
                            f"imagebind_vector_{i}",
                            data=imagebind_vec,
                            compression="gzip",
                            chunks=True,
                        )

                # Save metadata as JSON attributes
                f.attrs["total_bundles"] = len(feature_bundles)
                f.attrs["format_version"] = "1.0"
                f.attrs["created"] = datetime.now().isoformat()

            logger.info(f"Successfully saved to {output_path}")
            return str(output_path)

        except Exception as e:
            logger.error(f"Failed to serialize to HDF5: {str(e)}")
            raise

    def deserialize_parquet(self, parquet_file: str) -> Dict[str, Any]:
        """
        Deserialize Parquet file.

        Args:
            parquet_file: Path to Parquet file

        Returns:
            Dictionary with deserialized data
        """
        logger.info(f"Deserializing Parquet: {parquet_file}")

        try:
            table = pq.read_table(parquet_file)
            df = table.to_pandas()

            result = {
                "format": "parquet",
                "rows": len(df),
                "columns": df.columns.tolist(),
                "data": df.to_dict(orient="records"),
            }

            logger.info(f"Successfully deserialized {len(df)} records")
            return result

        except Exception as e:
            logger.error(f"Failed to deserialize Parquet: {str(e)}")
            raise

    def deserialize_hdf5(self, hdf5_file: str) -> Dict[str, Any]:
        """
        Deserialize HDF5 file.

        Args:
            hdf5_file: Path to HDF5 file

        Returns:
            Dictionary with deserialized data
        """
        logger.info(f"Deserializing HDF5: {hdf5_file}")

        try:
            result = {
                "format": "hdf5",
                "metadata": {},
                "vectors": {},
            }

            with h5py.File(str(hdf5_file), "r") as f:
                # Read metadata
                if "metadata" in f:
                    for slide_id in f["metadata"].keys():
                        attrs = dict(f["metadata"][slide_id].attrs)
                        result["metadata"][slide_id] = attrs

                # Read vectors
                if "vectors" in f:
                    for key in f["vectors"].keys():
                        vec_data = f["vectors"][key][:]
                        result["vectors"][key] = {
                            "shape": vec_data.shape,
                            "dtype": str(vec_data.dtype),
                            "size": vec_data.size,
                        }

                # Read attributes
                result["total_bundles"] = f.attrs.get("total_bundles", 0)
                result["format_version"] = f.attrs.get("format_version", "unknown")
                result["created"] = f.attrs.get("created", "unknown")

            logger.info("Successfully deserialized HDF5 file")
            return result

        except Exception as e:
            logger.error(f"Failed to deserialize HDF5: {str(e)}")
            raise

    def get_storage_stats(self, file_path: str) -> Dict[str, Any]:
        """
        Get storage statistics for serialized file.

        Args:
            file_path: Path to serialized file

        Returns:
            Dictionary with storage stats
        """
        path = Path(file_path)

        if not path.exists():
            logger.warning(f"File not found: {file_path}")
            return {}

        size_bytes = path.stat().st_size
        size_mb = size_bytes / (1024 * 1024)

        return {
            "file_path": str(path),
            "size_bytes": size_bytes,
            "size_mb": round(size_mb, 2),
            "format": "parquet" if path.suffix == ".parquet" else "hdf5",
            "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
        }


class BatchSerializer:
    """Serialize entire batches of processed PPTs."""

    def __init__(self, output_dir: str = "batch_storage"):
        """Initialize batch serializer."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.feature_serializer = FeatureBundleSerializer(str(self.output_dir / "features"))

    def serialize_batch(
        self,
        batch_id: str,
        feature_bundles: List[Dict[str, Any]],
        format_type: str = "parquet",
    ) -> Dict[str, str]:
        """
        Serialize entire batch.

        Args:
            batch_id: Batch identifier
            feature_bundles: List of feature bundles
            format_type: Output format ('parquet' or 'hdf5')

        Returns:
            Dictionary with output file paths
        """
        results = {}

        if format_type == "parquet":
            output_file = f"batch_{batch_id}.parquet"
            results["parquet"] = self.feature_serializer.serialize_to_parquet(
                feature_bundles, output_file
            )

        elif format_type == "hdf5":
            output_file = f"batch_{batch_id}.h5"
            results["hdf5"] = self.feature_serializer.serialize_to_hdf5(
                feature_bundles, output_file
            )

        # Also save metadata as JSON
        metadata_file = self.output_dir / f"batch_{batch_id}_metadata.json"
        metadata = {
            "batch_id": batch_id,
            "total_bundles": len(feature_bundles),
            "created": datetime.now().isoformat(),
            "storage_format": format_type,
            "output_files": results,
        }

        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

        results["metadata"] = str(metadata_file)
        return results

    def deserialize_batch(self, batch_id: str, format_type: str = "parquet") -> Dict[str, Any]:
        """
        Deserialize batch.

        Args:
            batch_id: Batch identifier
            format_type: Format type ('parquet' or 'hdf5')

        Returns:
            Dictionary with deserialized data
        """
        if format_type == "parquet":
            file_path = self.output_dir / f"batch_{batch_id}.parquet"
            return self.feature_serializer.deserialize_parquet(str(file_path))

        elif format_type == "hdf5":
            file_path = self.output_dir / f"batch_{batch_id}.h5"
            return self.feature_serializer.deserialize_hdf5(str(file_path))

        else:
            logger.error(f"Unknown format: {format_type}")
            return {}
