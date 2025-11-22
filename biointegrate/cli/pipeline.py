"""
pipeline.py

CLI principal que orquesta todo el pipeline de Estándares de Datos:
1. Presentación del proyecto y confirmación del usuario
2. Descarga de datos (GDC, HGNC, UniProt)
3. Creación de base de datos JSON (y opcionalmente inserción en MongoDB)
4. Evaluación de calidad de los JSON generados

Uso:
    datastandards-pipeline --data-config config/data/mario_data_config.yaml \\
                           --mongo-config config/db_mongo/mario_mongodb_config.yaml

    # Solo crear JSONs sin insertar en MongoDB:
    datastandards-pipeline --data-config config.yaml --mongo-config mongo.yaml --no-insert

    # Omitir descarga de datos (si ya existen):
    datastandards-pipeline --data-config config.yaml --mongo-config mongo.yaml --skip-download
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Any, Optional

# Importaciones internas
from DataStandards.data.config import (
    AppConfig,
    load_app_config,
    load_gdc_mongo_config,
    load_hgnc_mongo_config,
    load_uniprot_mongo_config,
)
from DataStandards.cli.presentation import show_presentation
from DataStandards.cli.data import (
    download_gdc_data,
    download_hgnc_data,
    download_uniprot_data,
)
from DataStandards.db.import_gdc_mongo import run_import as run_gdc_import
from DataStandards.db.import_hgnc_mongo import run_import as run_hgnc_import
from DataStandards.db.import_uniprot_mongo import run_import as run_uniprot_import
from DataStandards.quality.evaluate import run_quality_evaluation


# Configuración del logger
logger = logging.getLogger(__name__)


def configure_logging(level: int = logging.INFO, log_file: Optional[str] = None) -> None:
    """
    Configura el sistema de logging para el pipeline.

    Parameters
    ----------
    level : int
        Nivel de logging (DEBUG, INFO, WARNING, ERROR).
    log_file : str, optional
        Ruta a fichero de log. Si se especifica, también se escribe a fichero.
    """
    handlers = [logging.StreamHandler(sys.stdout)]

    if log_file:
        file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
        handlers.append(file_handler)

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )


def print_step_header(step_num: int, total_steps: int, title: str) -> None:
    """Imprime el encabezado de un paso del pipeline."""
    print()
    print("=" * 100)
    print(f"[{step_num}/{total_steps}] {title}")
    print("=" * 100)
    logger.info(f"[{step_num}/{total_steps}] {title}")


def run_download_step(data_config: AppConfig) -> bool:
    """
    Ejecuta el paso de descarga de datos.

    Parameters
    ----------
    data_config : AppConfig
        Configuración de descarga de datos.

    Returns
    -------
    bool
        True si la descarga fue exitosa, False en caso contrario.
    """
    errors = []

    # Descargar GDC
    print("\n--- Descargando datos GDC ---")
    try:
        download_gdc_data(data_config)
        print("  GDC: OK")
    except Exception as e:
        error_msg = f"Error en descarga GDC: {e}"
        logger.error(error_msg)
        errors.append(error_msg)
        print(f"  GDC: ERROR - {e}")

    # Descargar HGNC
    print("\n--- Descargando datos HGNC ---")
    try:
        download_hgnc_data(data_config)
        print("  HGNC: OK")
    except Exception as e:
        error_msg = f"Error en descarga HGNC: {e}"
        logger.error(error_msg)
        errors.append(error_msg)
        print(f"  HGNC: ERROR - {e}")

    # Descargar UniProt
    print("\n--- Descargando datos UniProt ---")
    try:
        download_uniprot_data(data_config)
        print("  UniProt: OK")
    except Exception as e:
        error_msg = f"Error en descarga UniProt: {e}"
        logger.error(error_msg)
        errors.append(error_msg)
        print(f"  UniProt: ERROR - {e}")

    if errors:
        print(f"\nDescarga completada con {len(errors)} error(es)")
        for err in errors:
            print(f"  - {err}")
        return False

    print("\nDescarga completada exitosamente")
    return True


def run_json_creation_step(
    mongo_config_path: Path,
    no_insert: bool = False,
    quiet: bool = False,
) -> tuple[bool, dict[str, Optional[str]]]:
    """
    Ejecuta el paso de creación de JSONs y opcionalmente inserta en MongoDB.

    Parameters
    ----------
    mongo_config_path : Path
        Ruta al fichero de configuración de MongoDB.
    no_insert : bool
        Si True, solo crea JSONs sin insertar en MongoDB.
    quiet : bool
        Si True, reduce la verbosidad.

    Returns
    -------
    tuple[bool, dict[str, Optional[str]]]
        (éxito, rutas_json) donde rutas_json contiene las rutas a los JSONs generados.
    """
    errors = []
    json_paths: dict[str, Optional[str]] = {
        "GDC": None,
        "HGNC": None,
        "UniProt": None,
    }

    # Importar GDC
    print("\n--- Procesando datos GDC ---")
    try:
        config = load_gdc_mongo_config(mongo_config_path)
        if no_insert:
            config.options.insert_into_mongodb = False
        if quiet:
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
            verbose=config.options.verbose,
        )
        json_paths["GDC"] = config.options.save_as_json_gdc
        print("  GDC: OK")
        if json_paths["GDC"]:
            print(f"    JSON: {json_paths['GDC']}")
    except Exception as e:
        error_msg = f"Error en procesamiento GDC: {e}"
        logger.error(error_msg, exc_info=True)
        errors.append(error_msg)
        print(f"  GDC: ERROR - {e}")

    # Importar HGNC
    print("\n--- Procesando datos HGNC ---")
    try:
        config = load_hgnc_mongo_config(mongo_config_path)
        if no_insert:
            config.options.insert_into_mongodb = False
        if quiet:
            config.options.verbose = False

        run_hgnc_import(
            hgnc_config=config.hgnc,
            gdc_config=config.gdc,
            mongo_uri=config.mongodb.mongo_uri,
            database_name=config.mongodb.database_name,
            insert_into_mongodb=config.options.insert_into_mongodb,
            drop_collection=config.options.drop_collection,
            save_as_json_hgnc=config.options.save_as_json_hgnc,
            verbose=config.options.verbose,
        )
        json_paths["HGNC"] = config.options.save_as_json_hgnc
        print("  HGNC: OK")
        if json_paths["HGNC"]:
            print(f"    JSON: {json_paths['HGNC']}")
    except Exception as e:
        error_msg = f"Error en procesamiento HGNC: {e}"
        logger.error(error_msg, exc_info=True)
        errors.append(error_msg)
        print(f"  HGNC: ERROR - {e}")

    # Importar UniProt
    print("\n--- Procesando datos UniProt ---")
    try:
        config = load_uniprot_mongo_config(mongo_config_path)
        if no_insert:
            config.options.insert_into_mongodb = False
        if quiet:
            config.options.verbose = False

        run_uniprot_import(
            uniprot_config=config.uniprot,
            mongo_uri=config.mongodb.mongo_uri,
            database_name=config.mongodb.database_name,
            collection_name=config.mongodb.collection_name,
            insert_into_mongodb=config.options.insert_into_mongodb,
            drop_collection=config.options.drop_collection,
            save_as_json_uniprot=config.options.save_as_json_uniprot,
            verbose=config.options.verbose,
        )
        json_paths["UniProt"] = config.options.save_as_json_uniprot
        print("  UniProt: OK")
        if json_paths["UniProt"]:
            print(f"    JSON: {json_paths['UniProt']}")
    except Exception as e:
        error_msg = f"Error en procesamiento UniProt: {e}"
        logger.error(error_msg, exc_info=True)
        errors.append(error_msg)
        print(f"  UniProt: ERROR - {e}")

    if errors:
        print(f"\nCreación de JSON completada con {len(errors)} error(es)")
        for err in errors:
            print(f"  - {err}")
        return False, json_paths

    action = "creados (sin inserción MongoDB)" if no_insert else "creados e insertados en MongoDB"
    print(f"\nDocumentos JSON {action} exitosamente")
    return True, json_paths


def run_quality_step(json_paths: dict[str, Optional[str]]) -> bool:
    """
    Ejecuta el paso de evaluación de calidad.

    Parameters
    ----------
    json_paths : dict[str, Optional[str]]
        Diccionario con rutas a los JSONs generados.

    Returns
    -------
    bool
        True si la evaluación fue exitosa (todos los JSONs son válidos).
    """
    reports = run_quality_evaluation(
        gdc_json_path=json_paths.get("GDC"),
        hgnc_json_path=json_paths.get("HGNC"),
        uniprot_json_path=json_paths.get("UniProt"),
        verbose=True,
    )

    all_valid = all(r.is_valid for r in reports.values()) if reports else False
    return all_valid


def parse_args() -> argparse.Namespace:
    """
    Parsea los argumentos de línea de comandos.

    Returns
    -------
    argparse.Namespace
        Argumentos parseados.
    """
    parser = argparse.ArgumentParser(
        description="Pipeline completo de Estándares de Datos: descarga, transformación y evaluación.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  # Pipeline completo con inserción en MongoDB:
  %(prog)s --data-config config/data/mario_data_config.yaml \\
           --mongo-config config/db_mongo/mario_mongodb_config.yaml

  # Solo crear JSONs sin insertar en MongoDB:
  %(prog)s --data-config config.yaml --mongo-config mongo.yaml --no-insert

  # Omitir descarga (datos ya existen):
  %(prog)s --data-config config.yaml --mongo-config mongo.yaml --skip-download

  # Omitir evaluación de calidad:
  %(prog)s --data-config config.yaml --mongo-config mongo.yaml --skip-quality

  # Modo silencioso (sin confirmación):
  %(prog)s --data-config config.yaml --mongo-config mongo.yaml --yes
        """,
    )

    # Argumentos requeridos
    parser.add_argument(
        "--data-config",
        type=str,
        required=True,
        help="Ruta al fichero YAML de configuración de datos (descarga).",
    )

    parser.add_argument(
        "--mongo-config",
        type=str,
        required=True,
        help="Ruta al fichero YAML de configuración de MongoDB (importación).",
    )

    # Opciones de control del pipeline
    parser.add_argument(
        "--no-insert",
        action="store_true",
        help="Solo crear JSONs, no insertar en MongoDB.",
    )

    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Omitir paso de descarga de datos (asumir que ya existen).",
    )

    parser.add_argument(
        "--skip-quality",
        action="store_true",
        help="Omitir paso de evaluación de calidad.",
    )

    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Saltar confirmación del usuario (ejecutar directamente).",
    )

    # Opciones de logging
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Activar modo verbose (nivel DEBUG).",
    )

    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Modo silencioso (solo errores críticos).",
    )

    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Guardar logs en fichero (además de stdout).",
    )

    return parser.parse_args()


def main() -> None:
    """
    Punto de entrada principal del pipeline.

    Ejecuta todos los pasos del pipeline:
    1. Presentación y confirmación
    2. Descarga de datos
    3. Creación de JSONs (y opcionalmente inserción en MongoDB)
    4. Evaluación de calidad
    """
    args = parse_args()

    # Configurar logging
    if args.quiet:
        log_level = logging.ERROR
    elif args.verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    configure_logging(log_level, args.log_file)

    # Validar rutas de configuración
    data_config_path = Path(args.data_config).expanduser().resolve()
    mongo_config_path = Path(args.mongo_config).expanduser().resolve()

    if not data_config_path.exists():
        logger.error(f"Fichero de configuración de datos no encontrado: {data_config_path}")
        sys.exit(1)

    if not mongo_config_path.exists():
        logger.error(f"Fichero de configuración de MongoDB no encontrado: {mongo_config_path}")
        sys.exit(1)

    # Cargar configuraciones
    logger.info(f"Cargando configuración de datos: {data_config_path}")
    try:
        data_config = load_app_config(data_config_path)
    except Exception as e:
        logger.error(f"Error al cargar configuración de datos: {e}")
        sys.exit(1)

    logger.info(f"Cargando configuración de MongoDB: {mongo_config_path}")
    try:
        mongo_config = load_gdc_mongo_config(mongo_config_path)
    except Exception as e:
        logger.error(f"Error al cargar configuración de MongoDB: {e}")
        sys.exit(1)

    # Calcular número de pasos
    total_steps = 0
    if not args.skip_download:
        total_steps += 1
    total_steps += 1  # Creación de JSON siempre
    if not args.skip_quality:
        total_steps += 1

    # Mostrar presentación y solicitar confirmación
    if not args.yes:
        confirmed = show_presentation(
            data_config_path=data_config_path,
            mongo_config_path=mongo_config_path,
            data_config=data_config,
            mongo_config=mongo_config,
            no_insert=args.no_insert,
            skip_download=args.skip_download,
            skip_quality=args.skip_quality,
        )
        if not confirmed:
            logger.info("Pipeline cancelado por el usuario")
            sys.exit(0)
    else:
        logger.info("Modo --yes: saltando confirmación")

    # Registrar tiempo de inicio
    start_time = time.time()
    current_step = 0
    success = True
    json_paths: dict[str, Optional[str]] = {}

    try:
        # Paso 1: Descarga de datos
        if not args.skip_download:
            current_step += 1
            print_step_header(current_step, total_steps, "DESCARGA DE DATOS")
            download_success = run_download_step(data_config)
            if not download_success:
                logger.warning("Descarga completada con errores, continuando...")

        # Paso 2: Creación de JSONs (y opcionalmente MongoDB)
        current_step += 1
        title = "CREACIÓN DE BASE DE DATOS JSON"
        if not args.no_insert:
            title += " E INSERCIÓN EN MONGODB"
        print_step_header(current_step, total_steps, title)

        json_success, json_paths = run_json_creation_step(
            mongo_config_path=mongo_config_path,
            no_insert=args.no_insert,
            quiet=args.quiet,
        )
        if not json_success:
            logger.warning("Creación de JSON completada con errores")
            success = False

        # Paso 3: Evaluación de calidad
        if not args.skip_quality:
            current_step += 1
            print_step_header(current_step, total_steps, "EVALUACIÓN DE CALIDAD")
            quality_success = run_quality_step(json_paths)
            if not quality_success:
                logger.warning("Evaluación de calidad detectó problemas")
                # No marcamos success = False porque es solo validación

    except KeyboardInterrupt:
        print("\n\nPipeline interrumpido por el usuario")
        logger.warning("Pipeline interrumpido por el usuario")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Error fatal en el pipeline: {e}", exc_info=True)
        sys.exit(1)

    # Resumen final
    elapsed_time = time.time() - start_time
    minutes = int(elapsed_time // 60)
    seconds = int(elapsed_time % 60)

    print()
    print("=" * 100)
    print("PIPELINE COMPLETADO")
    print("=" * 100)
    print(f"  Estado:           {'EXITOSO' if success else 'COMPLETADO CON ERRORES'}")
    print(f"  Tiempo total:     {minutes}m {seconds}s")
    print(f"  Descarga:         {'Omitida' if args.skip_download else 'Ejecutada'}")
    print(f"  JSONs creados:    Sí")
    print(f"  MongoDB:          {'No (--no-insert)' if args.no_insert else 'Sí'}")
    print(f"  Evaluación:       {'Omitida' if args.skip_quality else 'Ejecutada'}")

    if json_paths:
        print("\n  Ficheros JSON generados:")
        for source, path in json_paths.items():
            if path:
                print(f"    - {source}: {path}")

    print("=" * 100)

    if not success:
        sys.exit(1)

    logger.info("Pipeline completado exitosamente")


if __name__ == "__main__":
    main()
