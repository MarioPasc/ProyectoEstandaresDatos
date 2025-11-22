"""
uniprot_config.py

Script de configuración para el importador UniProt a MongoDB.
Lee la configuración desde un archivo YAML y ejecuta la importación.

Uso:
    python DataStandards/db/uniprot_config.py --config config/db_mongo/mario_mongodb_config.yaml

    # O con el script instalado:
    datastandards-import-uniprot --config config/db_mongo/mario_mongodb_config.yaml
"""

import argparse
import sys
from pathlib import Path

# Importar el loader de configuración
from biointegrate.data.config import load_uniprot_mongo_config

# Importar la función principal de importación
from biointegrate.db.import_uniprot_mongo import run_import


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Importador de datos UniProt a MongoDB',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:

  # Importar con configuración por defecto
  %(prog)s --config config/db_mongo/mario_mongodb_config.yaml

  # Eliminar colección antes de importar (útil para rehacer la carga)
  %(prog)s --config config/db_mongo/mario_mongodb_config.yaml --drop-collection

  # Solo generar JSON sin insertar en MongoDB (útil para testing)
  %(prog)s --config config/db_mongo/mario_mongodb_config.yaml --no-insert-mongo

  # Modo silencioso (sin mensajes detallados)
  %(prog)s --config config/db_mongo/mario_mongodb_config.yaml --quiet

  # Guardar colección como JSON en ruta específica
  %(prog)s --config config/db_mongo/mario_mongodb_config.yaml --save-json /ruta/export.json

  # No guardar como JSON (ignorar configuración YAML)
  %(prog)s --config config/db_mongo/mario_mongodb_config.yaml --no-save-json

Campos clave en el documento MongoDB resultante:
  - _id: 'uniprot_multi_project'
  - uniprot_entries[].uniprot_id: ID de UniProt (usado para joins)
  - uniprot_entries[].projects.<PROJECT_ID>: Información por proyecto
  - uniprot_entries[].gene.hgnc_ids: IDs de HGNC (usado para joins)
  - uniprot_entries[].gene.ensembl_gene_ids: IDs de Ensembl (usado para joins)
"""
    )

    parser.add_argument(
        '--config',
        type=str,
        default='config/db_mongo/mario_mongodb_config.yaml',
        help='Ruta al archivo de configuración YAML (default: config/db_mongo/mario_mongodb_config.yaml)'
    )

    parser.add_argument(
        '--drop-collection',
        action='store_true',
        help='Eliminar la colección antes de importar (rehacer la carga completa)'
    )

    parser.add_argument(
        '--no-insert',
        action='store_true',
        help='Solo generar JSON sin insertar en MongoDB (útil para testing)'
    )

    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Modo silencioso (sin mensajes detallados)'
    )

    parser.add_argument(
        '--save-json',
        type=str,
        default=None,
        help='Ruta donde guardar el documento como JSON (sobrescribe configuración YAML)'
    )

    parser.add_argument(
        '--no-save-json',
        action='store_true',
        help='No guardar el documento como JSON (sobrescribe configuración YAML)'
    )

    return parser.parse_args()


def main():
    """Función principal del script."""

    # Parsear argumentos
    args = parse_args()

    # Verificar que el archivo de configuración existe
    config_path = Path(args.config).expanduser().resolve()
    if not config_path.exists():
        print(f"Error: Archivo de configuración no encontrado: {config_path}")
        print(f"\nAsegúrate de que el archivo existe o especifica una ruta diferente con --config")
        sys.exit(1)

    # Cargar configuración
    try:
        config = load_uniprot_mongo_config(config_path)
    except Exception as e:
        print(f"Error cargando configuración desde {config_path}: {e}")
        sys.exit(1)

    # Sobrescribir opciones con argumentos de línea de comandos
    if args.drop_collection:
        config.options.drop_collection = True

    if args.no_insert:
        config.options.insert_into_mongodb = False

    if args.quiet:
        config.options.verbose = False

    # Manejo de save_json
    if args.no_save_json:
        config.options.save_as_json_uniprot = None
    elif args.save_json is not None:
        config.options.save_as_json_uniprot = args.save_json

    # Si no se inserta en MongoDB pero no hay save_as_json_uniprot, usar valor por defecto
    if not config.options.insert_into_mongodb and not config.options.save_as_json_uniprot:
        config.options.save_as_json_uniprot = "uniprot_multi_project_export.json"

    # Ejecutar importación multi-proyecto
    try:
        run_import(
            # UniProt configuration with projects list
            uniprot_config=config.uniprot,

            # Conexión MongoDB
            mongo_uri=config.mongodb.mongo_uri,
            database_name=config.mongodb.database_name,
            collection_name=config.mongodb.collection_name,

            # Opciones
            insert_into_mongodb=config.options.insert_into_mongodb,
            drop_collection=config.options.drop_collection,
            save_as_json_uniprot=config.options.save_as_json_uniprot,
            verbose=config.options.verbose
        )
    except FileNotFoundError as e:
        print(f"\nError: {e}")
        print("\nAsegúrate de haber descargado los datos UniProt primero:")
        print("  datastandards-download --config config/data/mario_data_config.yaml --source uniprot")
        sys.exit(1)
    except Exception as e:
        print(f"\nError durante la importación: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
