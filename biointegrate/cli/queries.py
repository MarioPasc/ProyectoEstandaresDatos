"""
CLI for executing MongoDB queries from external specification files.

This module provides a command-line interface for:
- Loading MongoDB credentials from YAML config
- Parsing query specification files (find/aggregate)
- Executing queries against MongoDB
- Saving results as JSON files
- [T2] Transforming results to XML and applying XSLT to generate HTML

Output Directory Structure:
- JSON-only mode (no --xslt): Saves to output-dir/*.json
- Full transformation mode (--xslt): Creates json/, xml/, html/ subdirectories
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

# Importaciones internas existentes
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

# [NUEVO] Importaciones para la tarea T2
from biointegrate.t2.transform import json_to_xml, save_xml, apply_xslt

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
        description="Execute MongoDB queries and apply XSLT transformations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Execute queries and save as JSON
  biointegrate-execute-queries \\
    --config config.yaml \\
    --queries q1.txt \\
    --output-dir results/

  # [T2] Execute, transform to XML and generate HTML via XSLT
  # Creates results/json/, results/xml/, results/html/ subdirectories
  biointegrate-execute-queries \\
    --config config.yaml \\
    --queries q1.txt \\
    --output-dir results/ \\
    --xslt templates/report.xslt
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

    # [NUEVO] Argumentos para T2
    parser.add_argument(
        "--xslt",
        type=str,
        default=None,
        help="[T2] Path to XSLT transformation file for JSON->XML->HTML conversion. Requires --output-dir.",
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

        # 7. [NUEVO T2] Validación: Si se proporciona --xslt, se requiere --output-dir
        if args.xslt and not args.output_dir:
            logger.error("--xslt requires --output-dir to be specified")
            print("Error: --xslt requires --output-dir to be specified")
            return 1

        # 8. Procesamiento según modo (JSON-only vs Full transformation)
        if args.xslt:
            # MODO COMPLETO: JSON + XML + HTML en subdirectorios
            base_output_dir = Path(args.output_dir).expanduser().resolve()
            json_dir = base_output_dir / "json"
            xml_dir = base_output_dir / "xml"
            html_dir = base_output_dir / "html"

            xslt_path = Path(args.xslt).expanduser().resolve()

            logger.info("--- Starting T2 Transformation Pipeline ---")
            logger.info(f"Output directory structure:")
            logger.info(f"  JSON: {json_dir}")
            logger.info(f"  XML:  {xml_dir}")
            logger.info(f"  HTML: {html_dir}")
            logger.info(f"Using XSLT template: {xslt_path}")

            # Guardar JSON en subdirectorio
            logger.info(f"Saving JSON results to {json_dir}")
            save_results_to_files(results, json_dir)

            # Transformar cada query: JSON -> XML -> HTML
            for query_name, documents in results.items():
                try:
                    # A. Convertir JSON (lista de dicts) a Árbol XML
                    logger.info(f"Transforming '{query_name}' to XML...")
                    xml_tree = json_to_xml(documents, root_tag="results")

                    # B. Guardar XML en subdirectorio
                    xml_file = xml_dir / f"{query_name}.xml"
                    save_xml(xml_tree, xml_file)
                    logger.info(f"Saved XML to {xml_file}")

                    # C. Aplicar XSLT para generar HTML
                    html_file = html_dir / f"{query_name}.html"
                    logger.info(f"Applying XSLT -> {html_file}")
                    apply_xslt(xml_file, xslt_path, html_file)

                except Exception as e:
                    logger.error(f"Failed to transform query '{query_name}': {e}")
                    # No detenemos el loop, intentamos con la siguiente query

        elif args.output_dir:
            # MODO JSON-ONLY: Guardar solo JSON en la raíz de output-dir
            base_output_dir = Path(args.output_dir).expanduser().resolve()
            logger.info(f"Saving JSON results to {base_output_dir}")
            save_results_to_files(results, base_output_dir)

        logger.info("✓ All queries processed successfully")
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