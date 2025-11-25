"""
CLI for executing MongoDB queries from external specification files.

This module provides a command-line interface for:
- Loading MongoDB credentials from YAML config
- Parsing query specification files (find/aggregate)
- Executing queries against MongoDB
- Saving results as JSON files
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

from biointegrate.data.config import load_query_config
from biointegrate.queries.mongo_executor import (
    MongoConnectionError,
    QueryExecutionError,
    run_mongo_queries,
)
from biointegrate.queries.query_parser import (
    QueryFileNotFoundError,
    QuerySpecError,
    load_queries,
    parse_queries_arg,
)

logger = logging.getLogger(__name__)


def configure_logging(level_str: str = "INFO") -> None:
    """Configure logging for CLI."""
    level = getattr(logging, level_str.upper(), logging.INFO)
    logging.basicConfig(
        level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )


def save_results_to_files(
    results: Dict[str, List[Dict[str, Any]]], output_dir: Path
) -> None:
    """
    Save query results to individual JSON files.

    Args:
        results: Dictionary mapping query name to documents
        output_dir: Directory to save result files
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    for query_name, documents in results.items():
        output_file = output_dir / f"{query_name}.json"
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(documents, f, indent=2, ensure_ascii=False, default=str)
            logger.info(f"Saved {len(documents)} docs to {output_file}")
        except Exception as e:
            logger.error(f"Failed to save {output_file}: {e}")


def print_summary(results: Dict[str, List[Dict[str, Any]]]) -> None:
    """Print execution summary to stdout."""
    print("\n" + "=" * 60)
    print("QUERY EXECUTION SUMMARY")
    print("=" * 60)
    for query_name, documents in results.items():
        print(f"  {query_name}: {len(documents)} documents")
    print("=" * 60 + "\n")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Execute MongoDB queries from specification files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Execute single query with default config
  biointegrate-execute-queries \\
    --config config/queries/mario_queries.yaml \\
    --queries queries/q1.txt

  # Execute multiple queries and save results
  biointegrate-execute-queries \\
    --config config/queries/mario_queries.yaml \\
    --queries queries/q1.txt,queries/q2.txt,queries/q3.txt \\
    --output-dir results/

  # Dry run (validate config and queries without executing)
  biointegrate-execute-queries \\
    --config config/queries/mario_queries.yaml \\
    --queries queries/q1.txt,queries/q2.txt \\
    --dry-run

Config YAML format:
  mongo:
    uri: "mongodb://localhost:27017/"
    database: "estandares_db"
  execution:
    default_limit: 100
    timeout_s: 30
  logging:
    level: "INFO"

Query file format (JSON):
  {
    "name": "hgnc_find",
    "collection": "hgnc_genes",
    "type": "find",
    "filter": {"symbol": "TP53"},
    "projection": {"_id": 0, "symbol": 1, "hgnc_id": 1}
  }
        """,
    )

    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to YAML configuration file (MongoDB credentials)",
    )

    parser.add_argument(
        "--queries",
        type=str,
        required=True,
        help="Comma-separated list of query specification files (e.g., q1.txt,q2.txt)",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory to save query results as JSON files (optional)",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Override logging level from config",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config and queries without executing against MongoDB",
    )

    # Placeholder for future T2 features
    parser.add_argument(
        "--xslt",
        type=str,
        default=None,
        help="(Not implemented) XSLT transformation file for JSON→XML→HTML",
    )

    parser.add_argument(
        "--output-html-dir",
        type=str,
        default=None,
        help="(Not implemented) Directory for HTML output files",
    )

    return parser.parse_args()


def main() -> int:
    """Main CLI entry point."""
    args = parse_args()

    try:
        # 1. Load configuration
        logger.info(f"Loading configuration from {args.config}")
        config = load_query_config(args.config)

        # Configure logging (CLI flag overrides config)
        log_level = args.log_level or config.logging.level
        configure_logging(log_level)

        logger.info(f"Target database: {config.mongo.database}")

        # 2. Parse query file paths
        logger.info(f"Parsing query file paths: {args.queries}")
        query_paths = parse_queries_arg(args.queries)
        logger.info(f"Found {len(query_paths)} query files")

        # 3. Load and validate query specifications
        logger.info("Loading query specifications...")
        queries = load_queries(query_paths)
        logger.info(f"Loaded {len(queries)} valid queries")

        for query in queries:
            logger.debug(f"  - {query.name} ({query.type} on {query.collection})")

        # 4. Dry run mode: exit early
        if args.dry_run:
            logger.info(
                "DRY RUN MODE: Configuration and queries validated successfully"
            )
            print("\n✓ Dry run completed successfully")
            print(f"  Config: {args.config}")
            print(f"  Queries: {len(queries)} validated")
            return 0

        # 5. Execute queries
        logger.info("Executing queries against MongoDB...")
        results = run_mongo_queries(
            queries=queries,
            mongo_uri=config.mongo.mongo_uri,
            database_name=config.mongo.database,
            timeout_s=config.execution.timeout_s,
        )

        # 6. Output results
        print_summary(results)

        # 7. Save to files if requested
        if args.output_dir:
            output_dir = Path(args.output_dir).expanduser().resolve()
            logger.info(f"Saving results to {output_dir}")
            save_results_to_files(results, output_dir)

        logger.info("✓ All queries executed successfully")
        return 0

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return 1
    except (QueryFileNotFoundError, QuerySpecError) as e:
        logger.error(f"Query specification error: {e}")
        return 1
    except MongoConnectionError as e:
        logger.error(f"MongoDB connection error: {e}")
        return 1
    except QueryExecutionError as e:
        logger.error(f"Query execution error: {e}")
        return 1
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        return 130
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
