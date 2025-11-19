"""
hgnc_config.py

Script de configuración para el importador HGNC a MongoDB.
Lee la configuración desde un archivo YAML y ejecuta la importación de genes HGNC
combinados con datos de expresión de GDC.

Uso:
    python DataStandards/db/hgnc_config.py --config config/db_mongo/mario_mongodb_config.yaml

    # O con el script instalado:
    datastandards-import-hgnc --config config/db_mongo/mario_mongodb_config.yaml

    # Solo guardar JSON (sin insertar en MongoDB):
    datastandards-import-hgnc --config config.yaml --only-json

Issue: #16 - HGNC + GDC Expression Integration
"""

import argparse
import sys
from pathlib import Path

# Importar el loader de configuración
from DataStandards.data.config import load_hgnc_mongo_config

# Importar la función principal de importación
from DataStandards.db.import_hgnc_mongo import run_import


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Importador de datos HGNC con expresión GDC a MongoDB',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:

  # Importar con configuración por defecto
  %(prog)s --config config/db_mongo/mario_mongodb_config.yaml

  # Eliminar colección antes de importar (útil para rehacer la carga)
  %(prog)s --config config/db_mongo/mario_mongodb_config.yaml --drop-collection

  # Solo guardar JSON, sin insertar en MongoDB
  %(prog)s --config config/db_mongo/mario_mongodb_config.yaml --only-json

  # Modo silencioso (sin mensajes detallados)
  %(prog)s --config config/db_mongo/mario_mongodb_config.yaml --quiet

  # Guardar colección como JSON en ruta específica
  %(prog)s --config config/db_mongo/mario_mongodb_config.yaml --save-json /ruta/export.json

  # No guardar como JSON (ignorar configuración YAML)
  %(prog)s --config config/db_mongo/mario_mongodb_config.yaml --no-save-json

Estructura del documento MongoDB resultante:
  - _id / hgnc_id: ID del gen HGNC (usado como clave principal)
  - symbol: Símbolo del gen (ej. TP53)
  - ensembl_gene_id: ID de Ensembl
  - uniprot_ids: Lista de IDs de UniProt
  - projects: Diccionario de proyectos GDC con datos de expresión
    - {project_id}:
      - n_cases: Número de casos con datos
      - cases:
        - {case_id}:
          - file_id: ID del fichero STAR-counts
          - unstranded: Valor de expresión unstranded
          - stranded_first: Valor de expresión stranded_first
          - stranded_second: Valor de expresión stranded_second
          - tpm_unstranded: TPM (Transcripts Per Million)
          - fpkm_unstranded: FPKM (Fragments Per Kilobase Million)
          - fpkm_uq_unstranded: FPKM Upper Quartile
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
        '--only-json',
        action='store_true',
        help='Solo guardar JSON, sin insertar en MongoDB'
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
        config = load_hgnc_mongo_config(config_path)
    except Exception as e:
        print(f"Error cargando configuración desde {config_path}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Sobrescribir opciones con argumentos de línea de comandos
    if args.drop_collection:
        config.options.drop_collection = True

    if args.quiet:
        config.options.verbose = False

    # Manejo de save_json
    if args.no_save_json:
        config.options.save_as_json_hgnc = None
    elif args.save_json is not None:
        config.options.save_as_json_hgnc = args.save_json

    # Ejecutar importación
    try:
        run_import(
            # HGNC configuration
            hgnc_config=config.hgnc,

            # GDC configuration with projects list
            gdc_config=config.gdc,

            # Conexión MongoDB
            mongo_uri=config.mongodb.mongo_uri,
            database_name=config.mongodb.database_name,

            # Opciones
            drop_collection=config.options.drop_collection,
            save_as_json_hgnc=config.options.save_as_json_hgnc,
            only_json=args.only_json,
            verbose=config.options.verbose
        )
    except FileNotFoundError as e:
        print(f"\nError: {e}")
        print("\nAsegúrate de haber descargado los datos HGNC y GDC primero:")
        print("  # Descargar HGNC:")
        print("  datastandards-download --config config/data/mario_data_config.yaml --source hgnc")
        print("\n  # Descargar GDC:")
        print("  datastandards-download --config config/data/mario_data_config.yaml --source gdc")
        sys.exit(1)
    except Exception as e:
        print(f"\nError durante la importación: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
