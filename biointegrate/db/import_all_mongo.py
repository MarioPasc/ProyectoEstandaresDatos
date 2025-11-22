"""
import_all_mongo.py

Unified importer for all data sources (GDC, HGNC, UniProt) to MongoDB.
Executes all three importers in sequence using a single configuration file.

Usage:
    python DataStandards/db/import_all_mongo.py --config config/db_mongo/mario_mongodb_config.yaml

    # Or with the script installed:
    datastandards-import-all --config config/db_mongo/mario_mongodb_config.yaml
"""

import argparse
import sys
from pathlib import Path

from biointegrate.data.config import (
    load_gdc_mongo_config,
    load_hgnc_mongo_config,
    load_uniprot_mongo_config
)
from biointegrate.db.import_gdc_mongo import run_import as run_gdc_import
from biointegrate.db.import_hgnc_mongo import run_import as run_hgnc_import
from biointegrate.db.import_uniprot_mongo import run_import as run_uniprot_import


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Unified importer for all data sources to MongoDB',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Imports all data sources in sequence:
  1. GDC (cases and expression data)
  2. HGNC (genes with expression data)
  3. UniProt (protein data)

Examples:
  # Import all with configuration
  %(prog)s --config config/db_mongo/mario_mongodb_config.yaml

  # Only generate JSONs without MongoDB insertion
  %(prog)s --config config/db_mongo/mario_mongodb_config.yaml --no-insert

  # Skip specific importers
  %(prog)s --config config.yaml --skip-gdc --skip-hgnc
"""
    )

    parser.add_argument(
        '--config',
        type=str,
        required=True,
        help='Path to YAML configuration file'
    )

    parser.add_argument(
        '--no-insert',
        action='store_true',
        help='Only generate JSONs, do not insert into MongoDB'
    )

    parser.add_argument(
        '--skip-gdc',
        action='store_true',
        help='Skip GDC import'
    )

    parser.add_argument(
        '--skip-hgnc',
        action='store_true',
        help='Skip HGNC import'
    )

    parser.add_argument(
        '--skip-uniprot',
        action='store_true',
        help='Skip UniProt import'
    )

    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Reduce verbosity'
    )

    return parser.parse_args()


def main():
    """Main function."""
    args = parse_args()

    # Verify config file exists
    config_path = Path(args.config).expanduser().resolve()
    if not config_path.exists():
        print(f"Error: Configuration file not found: {config_path}")
        sys.exit(1)

    print("=" * 100)
    print("UNIFIED MONGODB IMPORTER")
    print("=" * 100)
    print(f"Configuration: {config_path}")
    print(f"Insert into MongoDB: {not args.no_insert}")
    print("=" * 100)

    importers_to_run = []
    if not args.skip_gdc:
        importers_to_run.append("GDC")
    if not args.skip_hgnc:
        importers_to_run.append("HGNC")
    if not args.skip_uniprot:
        importers_to_run.append("UniProt")

    print(f"\nImporters to run: {', '.join(importers_to_run)}")
    print("=" * 100)

    errors = []

    # Import GDC
    if not args.skip_gdc:
        print("\n" + "=" * 100)
        print("[1/3] IMPORTING GDC DATA")
        print("=" * 100)
        try:
            config = load_gdc_mongo_config(config_path)
            if args.no_insert:
                config.options.insert_into_mongodb = False
            if args.quiet:
                config.options.verbose = False

            run_gdc_import(
                gdc_config=config.gdc,
                mongo_uri=config.mongodb.mongo_uri,
                database_name=config.mongodb.database_name,
                collection_name=config.mongodb.collection_name,
                insert_into_mongodb=config.options.insert_into_mongodb,
                process_expression=config.options.process_expression,
                max_files=config.options.max_files_to_process,
                drop_collection=config.options.drop_collection,
                save_as_json=config.options.save_as_json_gdc,
                verbose=config.options.verbose
            )
            print("✓ GDC import completed successfully")
        except Exception as e:
            error_msg = f"✗ GDC import failed: {e}"
            print(error_msg)
            errors.append(error_msg)
            if not args.quiet:
                import traceback
                traceback.print_exc()

    # Import HGNC
    if not args.skip_hgnc:
        print("\n" + "=" * 100)
        print("[2/3] IMPORTING HGNC DATA")
        print("=" * 100)
        try:
            config = load_hgnc_mongo_config(config_path)
            if args.no_insert:
                config.options.insert_into_mongodb = False
            if args.quiet:
                config.options.verbose = False

            run_hgnc_import(
                hgnc_config=config.hgnc,
                gdc_config=config.gdc,
                mongo_uri=config.mongodb.mongo_uri,
                database_name=config.mongodb.database_name,
                insert_into_mongodb=config.options.insert_into_mongodb,
                drop_collection=config.options.drop_collection,
                save_as_json_hgnc=config.options.save_as_json_hgnc,
                verbose=config.options.verbose
            )
            print("✓ HGNC import completed successfully")
        except Exception as e:
            error_msg = f"✗ HGNC import failed: {e}"
            print(error_msg)
            errors.append(error_msg)
            if not args.quiet:
                import traceback
                traceback.print_exc()

    # Import UniProt
    if not args.skip_uniprot:
        print("\n" + "=" * 100)
        print("[3/3] IMPORTING UNIPROT DATA")
        print("=" * 100)
        try:
            config = load_uniprot_mongo_config(config_path)
            if args.no_insert:
                config.options.insert_into_mongodb = False
            if args.quiet:
                config.options.verbose = False

            run_uniprot_import(
                uniprot_config=config.uniprot,
                mongo_uri=config.mongodb.mongo_uri,
                database_name=config.mongodb.database_name,
                collection_name=config.mongodb.collection_name,
                insert_into_mongodb=config.options.insert_into_mongodb,
                drop_collection=config.options.drop_collection,
                save_as_json_uniprot=config.options.save_as_json_uniprot,
                verbose=config.options.verbose
            )
            print("✓ UniProt import completed successfully")
        except Exception as e:
            error_msg = f"✗ UniProt import failed: {e}"
            print(error_msg)
            errors.append(error_msg)
            if not args.quiet:
                import traceback
                traceback.print_exc()

    # Summary
    print("\n" + "=" * 100)
    print("IMPORT SUMMARY")
    print("=" * 100)

    if errors:
        print(f"\n✗ Completed with {len(errors)} error(s):")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    else:
        print("\n✓ All imports completed successfully!")
        print("=" * 100)


if __name__ == "__main__":
    main()
