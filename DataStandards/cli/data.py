"""
CLI para descargar datos de diferentes fuentes (GDC, HGNC, UniProt).

Este módulo proporciona una interfaz de línea de comandos para descargar
datos de forma selectiva desde:
    - GDC (Genomic Data Commons)
    - HGNC (HUGO Gene Nomenclature Committee)
    - UniProt (Universal Protein Resource)
    - All (todas las fuentes)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from DataStandards.data.config import AppConfig, load_app_config
from DataStandards.data.entrypoints.access_gdc import (
    download_manifest,
    download_file_metadata,
    fetch_genes_table,
    load_gdc_token,
)
from DataStandards.data.entrypoints.access_hgnc import download_hgnc_complete_set
from DataStandards.data.entrypoints.access_uniprot import download_uniprot_data as download_uniprot_impl
from DataStandards.utils.check_downloaded_filelength import (
    check_gdc_files,
    check_hgnc_files,
    check_uniprot_files,
)


logger = logging.getLogger(__name__)


def configure_logging(level: int = logging.INFO) -> None:
    """
    Configura el sistema de logging para el CLI.
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def download_gdc_data(config: AppConfig) -> None:
    """
    Descarga todos los datos del GDC según la configuración.
    
    Parameters
    ----------
    config : AppConfig
        Configuración de la aplicación que incluye los parámetros de GDC.
    """
    logger.info("=== Iniciando descarga de datos GDC ===")
    gdc_cfg = config.gdc
    token = load_gdc_token(gdc_cfg.token_path)
    
    try:
        download_manifest(gdc_cfg, token)
        download_file_metadata(gdc_cfg, token)
        fetch_genes_table(gdc_cfg, token)
        
        # Verificar archivos descargados
        logger.info("Verificando archivos descargados...")
        check_gdc_files(
            manifest_path=gdc_cfg.manifest_output,
            file_metadata_path=gdc_cfg.file_metadata_output,
            genes_path=gdc_cfg.genes_output,
        )
        
        logger.info("=== Descarga de GDC completada exitosamente ===")
    except Exception as e:
        logger.error(f"Error al descargar datos de GDC: {e}")
        raise


def download_hgnc_data(config: AppConfig) -> None:
    """
    Descarga el conjunto completo de datos de HGNC.
    
    Parameters
    ----------
    config : AppConfig
        Configuración de la aplicación que incluye los parámetros de HGNC.
    """
    logger.info("=== Iniciando descarga de datos HGNC ===")
    try:
        download_hgnc_complete_set(config.hgnc)
        
        # Verificar archivo descargado
        logger.info("Verificando archivo descargado...")
        check_hgnc_files(config.hgnc.output_path)
        
        logger.info("=== Descarga de HGNC completada exitosamente ===")
    except Exception as e:
        logger.error(f"Error al descargar datos de HGNC: {e}")
        raise


def download_uniprot_data(config: AppConfig) -> None:
    """
    Descarga datos de UniProt según la configuración.
    
    Parameters
    ----------
    config : AppConfig
        Configuración de la aplicación que incluye los parámetros de UniProt.
    """
    logger.info("=== Iniciando descarga de datos UniProt ===")
    
    if config.uniprot is None:
        logger.warning("No se encontró configuración de UniProt en el fichero de configuración")
        logger.info("=== Descarga de UniProt omitida ===")
        return
    
    try:
        download_uniprot_impl(config.uniprot)
        
        # Verificar archivo descargado
        logger.info("Verificando archivo descargado...")
        check_uniprot_files(config.uniprot.output_path)
        
        logger.info("=== Descarga de UniProt completada exitosamente ===")
    except Exception as e:
        logger.error(f"Error al descargar datos de UniProt: {e}")
        raise


def download_all_data(config: AppConfig) -> None:
    """
    Descarga datos de todas las fuentes disponibles.
    
    Parameters
    ----------
    config : AppConfig
        Configuración de la aplicación con todos los parámetros.
    """
    logger.info("=== Iniciando descarga de TODAS las fuentes ===")
    
    # Descargar GDC
    try:
        download_gdc_data(config)
    except Exception as e:
        logger.error(f"Error en GDC, continuando con otras fuentes...")
    
    # Descargar HGNC
    try:
        download_hgnc_data(config)
    except Exception as e:
        logger.error(f"Error en HGNC, continuando con otras fuentes...")
    
    # Descargar UniProt
    try:
        download_uniprot_data(config)
    except Exception as e:
        logger.error(f"Error en UniProt, continuando con otras fuentes...")
    
    logger.info("=== Proceso de descarga completo ===")


def parse_args() -> argparse.Namespace:
    """
    Parsea los argumentos de línea de comandos.
    
    Returns
    -------
    argparse.Namespace
        Argumentos parseados.
    """
    parser = argparse.ArgumentParser(
        description="Descarga datos biomédicos de diferentes fuentes (GDC, HGNC, UniProt).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  %(prog)s --config config/data_config.yaml --source gdc
  %(prog)s --config config/data_config.yaml --source hgnc
  %(prog)s --config config/data_config.yaml --source uniprot
  %(prog)s --config config/data_config.yaml --source all
        """,
    )
    
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Ruta al fichero YAML de configuración (por ejemplo, config/data_config.yaml).",
    )
    
    parser.add_argument(
        "--source",
        type=str,
        choices=["gdc", "hgnc", "uniprot", "all"],
        required=True,
        help="Fuente de datos a descargar: 'gdc', 'hgnc', 'uniprot', o 'all' para todas.",
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Activar modo verbose (nivel DEBUG de logging).",
    )
    
    return parser.parse_args()


def main() -> None:
    """
    Punto de entrada principal del CLI.
    
    Carga la configuración y ejecuta la descarga de datos según la fuente seleccionada.
    """
    args = parse_args()
    
    # Configurar logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    configure_logging(log_level)
    
    # Cargar configuración
    config_path = Path(args.config).expanduser().resolve()
    if not config_path.exists():
        logger.error(f"El fichero de configuración no existe: {config_path}")
        sys.exit(1)
    
    logger.info(f"Cargando configuración desde: {config_path}")
    try:
        config = load_app_config(config_path)
    except Exception as e:
        logger.error(f"Error al cargar la configuración: {e}")
        sys.exit(1)
    
    # Ejecutar descarga según la fuente seleccionada
    try:
        if args.source == "gdc":
            download_gdc_data(config)
        elif args.source == "hgnc":
            download_hgnc_data(config)
        elif args.source == "uniprot":
            download_uniprot_data(config)
        elif args.source == "all":
            download_all_data(config)
        else:
            logger.error(f"Fuente no reconocida: {args.source}")
            sys.exit(1)
            
        logger.info("✓ Proceso completado exitosamente")
        
    except KeyboardInterrupt:
        logger.warning("Proceso interrumpido por el usuario")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Error fatal: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
