"""
gdc_config.py

Script de configuración para el importador GDC a MongoDB.
Lee la configuración desde un archivo YAML y ejecuta la importación.

Uso:
    python DataStandards/db/gdc_config.py --config config/db_mongo/mario_mongodb_config.yaml

    # O con el script instalado:
    datastandards-import-gdc --config config/db_mongo/mario_mongodb_config.yaml

Issue: T1 - GDC MongoDB Import Task
"""

import argparse
import sys
from pathlib import Path

# Importar el loader de configuración
from DataStandards.data.config import load_gdc_mongo_config

# Importar la función principal de importación
from DataStandards.db.import_gdc_mongo import run_import


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Importador de datos GDC a MongoDB',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:

  # Importar con configuración por defecto
  %(prog)s --config config/db_mongo/mario_mongodb_config.yaml

  # Eliminar colección antes de importar (útil para rehacer la carga)
  %(prog)s --config config/db_mongo/mario_mongodb_config.yaml --drop-collection

  # Importar solo metadatos sin procesar expresión
  %(prog)s --config config/db_mongo/mario_mongodb_config.yaml --no-expression

  # Procesar solo los primeros 10 ficheros (útil para testing)
  %(prog)s --config config/db_mongo/mario_mongodb_config.yaml --max-files 10

  # Modo silencioso (sin mensajes detallados)
  %(prog)s --config config/db_mongo/mario_mongodb_config.yaml --quiet

  # Guardar colección como JSON en ruta específica
  %(prog)s --config config/db_mongo/mario_mongodb_config.yaml --save-json /ruta/export.json

  # No guardar como JSON (ignorar configuración YAML)
  %(prog)s --config config/db_mongo/mario_mongodb_config.yaml --no-save-json

Campos clave en el documento MongoDB resultante:
  - project_id: ID del proyecto (usado para joins)
  - cases[].case_id: ID del caso (usado para joins)
  - cases[].files[].file_id: ID del fichero (usado para joins)
  - cases[].files[].expression_summary: Estadísticas de expresión
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
        '--no-expression',
        action='store_true',
        help='No procesar ficheros STAR-Counts (solo importar metadatos)'
    )

    parser.add_argument(
        '--max-files',
        type=int,
        default=None,
        help='Número máximo de ficheros a procesar (útil para testing)'
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
        help='Ruta donde guardar la colección como JSON después de importar (sobrescribe configuración YAML)'
    )

    parser.add_argument(
        '--no-save-json',
        action='store_true',
        help='No guardar la colección como JSON (sobrescribe configuración YAML)'
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
        config = load_gdc_mongo_config(config_path)
    except Exception as e:
        print(f"Error cargando configuración desde {config_path}: {e}")
        sys.exit(1)

    # Sobrescribir opciones con argumentos de línea de comandos
    if args.drop_collection:
        config.options.drop_collection = True

    if args.no_expression:
        config.options.process_expression = False

    if args.max_files is not None:
        config.options.max_files_to_process = args.max_files

    if args.quiet:
        config.options.verbose = False

    # Manejo de save_json
    if args.no_save_json:
        config.options.save_as_json = None
    elif args.save_json is not None:
        config.options.save_as_json = args.save_json

    # Ejecutar importación multi-proyecto
    try:
        run_import(
            # GDC configuration with projects list
            gdc_config=config.gdc,

            # Conexión MongoDB
            mongo_uri=config.mongodb.mongo_uri,
            database_name=config.mongodb.database_name,
            collection_name=config.mongodb.collection_name,

            # Opciones
            process_expression=config.options.process_expression,
            max_files=config.options.max_files_to_process,
            drop_collection=config.options.drop_collection,
            save_as_json=config.options.save_as_json,
            verbose=config.options.verbose
        )
    except FileNotFoundError as e:
        print(f"\nError: {e}")
        print("\nAsegúrate de haber descargado los datos GDC primero:")
        print("  datastandards-download --config config/data/mario_data_config.yaml --source gdc")
        sys.exit(1)
    except Exception as e:
        print(f"\nError durante la importación: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
