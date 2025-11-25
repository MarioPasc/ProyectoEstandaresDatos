"""
MongoDB query execution module.

This module provides functionality to execute parsed MongoDB queries
(find and aggregate) against a MongoDB database.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from biointegrate.queries.query_parser import MongoQuery

logger = logging.getLogger(__name__)


class MongoConnectionError(Exception):
    """Raised when MongoDB connection fails."""

    pass


class QueryExecutionError(Exception):
    """Raised when query execution fails."""

    pass


def run_mongo_query(
    query: MongoQuery,
    client: MongoClient,
    database_name: str,
    timeout_ms: int = 30000,
) -> List[Dict[str, Any]]:
    """
    Execute a single MongoDB query.

    Args:
        query: MongoQuery specification
        client: Active MongoClient instance
        database_name: Database name
        timeout_ms: Query timeout in milliseconds

    Returns:
        List of result documents

    Raises:
        QueryExecutionError: If query execution fails

    Example:
        >>> from pymongo import MongoClient
        >>> client = MongoClient("mongodb://localhost:27017/")
        >>> query = MongoQuery(name="test", collection="users", type="find", filter={})
        >>> results = run_mongo_query(query, client, "test_db")
    """
    try:
        db = client[database_name]
        collection = db[query.collection]

        if query.type == "find":
            cursor = collection.find(
                filter=query.filter, projection=query.projection
            ).max_time_ms(timeout_ms)
            results = list(cursor)

        elif query.type == "aggregate":
            cursor = collection.aggregate(pipeline=query.pipeline, maxTimeMS=timeout_ms)
            results = list(cursor)

        else:
            raise QueryExecutionError(f"Unsupported query type: {query.type}")

        logger.info(
            f"Query '{query.name}' on '{query.collection}': "
            f"{len(results)} documents returned"
        )
        return results

    except PyMongoError as e:
        raise QueryExecutionError(
            f"Failed to execute query '{query.name}' on '{query.collection}': {e}"
        )


def run_mongo_queries(
    queries: List[MongoQuery],
    mongo_uri: str,
    database_name: str,
    timeout_s: int = 30,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Execute multiple MongoDB queries sequentially.

    Args:
        queries: List of MongoQuery specifications
        mongo_uri: MongoDB connection URI
        database_name: Database name
        timeout_s: Query timeout in seconds

    Returns:
        Dictionary mapping query name to result documents

    Raises:
        MongoConnectionError: If connection fails
        QueryExecutionError: If any query fails

    Example:
        >>> queries = [
        ...     MongoQuery(name="q1", collection="users", type="find", filter={}),
        ...     MongoQuery(name="q2", collection="posts", type="find", filter={})
        ... ]
        >>> results = run_mongo_queries(queries, "mongodb://localhost:27017/", "test_db")
        >>> "q1" in results
        True
    """
    results = {}
    timeout_ms = timeout_s * 1000

    try:
        with MongoClient(mongo_uri, serverSelectionTimeoutMS=5000) as client:
            # Test connection
            client.admin.command("ping")
            logger.info(f"Connected to MongoDB: {database_name}")

            # Execute each query
            for query in queries:
                logger.info(
                    f"Executing query '{query.name}' "
                    f"(type={query.type}, collection={query.collection})"
                )
                query_results = run_mongo_query(
                    query=query,
                    client=client,
                    database_name=database_name,
                    timeout_ms=timeout_ms,
                )
                results[query.name] = query_results

    except PyMongoError as e:
        # Extract hostname from URI for error message (hide credentials)
        uri_display = mongo_uri.split("@")[-1] if "@" in mongo_uri else mongo_uri
        raise MongoConnectionError(f"Failed to connect to MongoDB at {uri_display}: {e}")

    return results
