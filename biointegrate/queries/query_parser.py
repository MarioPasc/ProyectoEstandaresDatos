"""
Parser for MongoDB query specification files.

This module provides functionality to parse query specifications from JSON/TXT files
and validate them according to the T2 query format specification.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional


@dataclass
class MongoQuery:
    """Represents a parsed MongoDB query specification."""

    name: str
    collection: str
    type: Literal["find", "aggregate"]

    # For find queries
    filter: Optional[Dict[str, Any]] = None
    projection: Optional[Dict[str, Any]] = None

    # For aggregate queries
    pipeline: Optional[List[Dict[str, Any]]] = None

    # Source file for logging
    source_file: Optional[str] = None


class QuerySpecError(Exception):
    """Raised when query specification is invalid."""

    pass


class QueryFileNotFoundError(FileNotFoundError):
    """Raised when query file doesn't exist."""

    pass


def parse_queries_arg(raw: str) -> List[Path]:
    """
    Parse comma-separated query file paths.

    Args:
        raw: Comma-separated paths like "q1.txt,q2.txt,q3.txt"

    Returns:
        List of validated Path objects

    Raises:
        QueryFileNotFoundError: If any file doesn't exist

    Example:
        >>> paths = parse_queries_arg("q1.txt,q2.txt")
        >>> len(paths)
        2
    """
    paths = []
    for part in raw.split(","):
        path = Path(part.strip()).expanduser().resolve()
        if not path.exists():
            raise QueryFileNotFoundError(f"Query file not found: {path}")
        paths.append(path)
    return paths


def parse_query_spec(path: Path) -> MongoQuery:
    """
    Parse a single query specification file.

    Expected JSON format:
    {
      "name": "query_identifier",
      "collection": "collection_name",
      "type": "find" | "aggregate",
      "filter": {...},        // for find
      "projection": {...},    // optional for find
      "pipeline": [...]       // for aggregate
    }

    Args:
        path: Path to query specification file

    Returns:
        Parsed MongoQuery object

    Raises:
        QuerySpecError: If spec is invalid or malformed

    Example:
        >>> from pathlib import Path
        >>> query = parse_query_spec(Path("queries/example.txt"))
        >>> query.name
        'example_query'
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            spec = json.load(f)
    except json.JSONDecodeError as e:
        raise QuerySpecError(f"Invalid JSON in {path}: {e}")
    except Exception as e:
        raise QuerySpecError(f"Error reading {path}: {e}")

    # Validate required fields
    if "name" not in spec:
        raise QuerySpecError(f"Missing 'name' field in {path}")
    if "collection" not in spec:
        raise QuerySpecError(f"Missing 'collection' field in {path}")
    if "type" not in spec:
        raise QuerySpecError(f"Missing 'type' field in {path}")

    query_type = spec["type"]
    if query_type not in ["find", "aggregate"]:
        raise QuerySpecError(
            f"Invalid type '{query_type}' in {path}. Must be 'find' or 'aggregate'"
        )

    # Validate type-specific fields
    if query_type == "find":
        if "filter" not in spec:
            raise QuerySpecError(f"Missing 'filter' for find query in {path}")
        return MongoQuery(
            name=spec["name"],
            collection=spec["collection"],
            type="find",
            filter=spec["filter"],
            projection=spec.get("projection"),
            source_file=str(path),
        )
    else:  # aggregate
        if "pipeline" not in spec:
            raise QuerySpecError(f"Missing 'pipeline' for aggregate query in {path}")
        if not isinstance(spec["pipeline"], list) or len(spec["pipeline"]) == 0:
            raise QuerySpecError(f"'pipeline' must be non-empty list in {path}")
        return MongoQuery(
            name=spec["name"],
            collection=spec["collection"],
            type="aggregate",
            pipeline=spec["pipeline"],
            source_file=str(path),
        )


def load_queries(paths: List[Path]) -> List[MongoQuery]:
    """
    Load and parse multiple query specification files.

    Args:
        paths: List of paths to query files

    Returns:
        List of parsed MongoQuery objects

    Raises:
        QuerySpecError: If any query spec is invalid

    Example:
        >>> from pathlib import Path
        >>> paths = [Path("q1.txt"), Path("q2.txt")]
        >>> queries = load_queries(paths)
        >>> len(queries)
        2
    """
    queries = []
    for path in paths:
        query = parse_query_spec(path)
        queries.append(query)
    return queries
