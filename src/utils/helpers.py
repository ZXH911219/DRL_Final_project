"""
Utility helper functions for file operations and common tasks.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


def ensure_dir(path: str) -> Path:
    """
    Ensure directory exists, create if needed.

    Args:
        path: Directory path

    Returns:
        Path object
    """
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def read_file(path: str) -> str:
    """
    Read text file.

    Args:
        path: File path

    Returns:
        File contents as string
    """
    return Path(path).read_text(encoding="utf-8")


def write_file(path: str, content: str) -> None:
    """
    Write text file.

    Args:
        path: File path
        content: Content to write
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def read_json(path: str) -> Dict[str, Any]:
    """
    Read JSON file.

    Args:
        path: JSON file path

    Returns:
        Parsed JSON as dict
    """
    return json.loads(read_file(path))


def write_json(path: str, data: Dict[str, Any], indent: int = 2) -> None:
    """
    Write JSON file.

    Args:
        path: JSON file path
        data: Data to write
        indent: JSON indentation
    """
    write_file(path, json.dumps(data, indent=indent, ensure_ascii=False))


def read_yaml(path: str) -> Dict[str, Any]:
    """
    Read YAML file.

    Args:
        path: YAML file path

    Returns:
        Parsed YAML as dict
    """
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def write_yaml(path: str, data: Dict[str, Any]) -> None:
    """
    Write YAML file.

    Args:
        path: YAML file path
        data: Data to write
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(str(p), "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
