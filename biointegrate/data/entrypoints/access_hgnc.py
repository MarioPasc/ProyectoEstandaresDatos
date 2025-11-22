"""
Script para descargar de forma programática el fichero completo de HGNC
(hgnc_complete_set.txt) usando la URL pública proporcionada por HGNC.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import requests

from biointegrate.data.config import AppConfig, HGNCConfig, load_app_config

logger = logging.getLogger(__name__)


def configure_logging(level: int = logging.INFO) -> None:
    """
    Configura el sistema de logging básico para el script.
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def download_hgnc_complete_set(config: HGNCConfig) -> Path:
    """
    Descarga el fichero hgnc_complete_set.txt desde la URL pública de HGNC
    y lo guarda en la ruta indicada por output_path.
    
    Si el archivo ya existe, no lo vuelve a descargar.
    
    Parameters
    ----------
    config : HGNCConfig
        Configuración de HGNC que incluye la URL y ruta de salida.
    
    Returns
    -------
    Path
        Ruta al archivo descargado o existente.
    """
    url = config.url
    output_path = Path(config.output_path).expanduser().resolve()
    
    logger.info("=" * 80)
    logger.info("INICIANDO PROCESO DE DESCARGA DE HGNC")
    logger.info("=" * 80)
    logger.info("URL de descarga: %s", url)
    logger.info("Ruta de salida: %s", output_path)
    
    # Verificar si el archivo ya existe
    if output_path.is_file():
        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        logger.info("El fichero HGNC ya existe en: %s", output_path)
        logger.info("Tamaño del fichero existente: %.2f MB", file_size_mb)
        logger.info("Se omite la descarga. Para forzar nueva descarga, elimine el fichero.")
        logger.info("=" * 80)
        return output_path
    
    # Crear directorio si no existe
    output_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Directorio de salida creado/verificado: %s", output_path.parent)

    logger.info("Iniciando descarga del conjunto completo de HGNC...")
    try:
        response = requests.get(url, stream=True, timeout=config.request_timeout)
        response.raise_for_status()
        
        # Obtener tamaño del archivo si está disponible
        total_size = int(response.headers.get('content-length', 0))
        if total_size > 0:
            logger.info("Tamaño del archivo a descargar: %.2f MB", total_size / (1024 * 1024))
        
        bytes_downloaded = 0
        with output_path.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    fh.write(chunk)
                    bytes_downloaded += len(chunk)
                    
                    # Log de progreso cada 10 MB
                    if bytes_downloaded % (10 * 1024 * 1024) < 8192:
                        logger.info("Descargados: %.2f MB", bytes_downloaded / (1024 * 1024))
        
        final_size_mb = bytes_downloaded / (1024 * 1024)
        logger.info("✓ Descarga completada exitosamente")
        logger.info("  - Bytes descargados: %.2f MB", final_size_mb)
        logger.info("  - Fichero guardado en: %s", output_path)
        
    except requests.RequestException as e:
        logger.error("Error al descargar el fichero de HGNC: %s", e)
        # Limpiar archivo parcial si existe
        if output_path.exists():
            output_path.unlink()
            logger.info("Archivo parcial eliminado debido al error")
        raise
    
    logger.info("=" * 80)
    return output_path


def parse_args() -> argparse.Namespace:
    """
    Parseo de argumentos de línea de comandos para el script.
    """
    parser = argparse.ArgumentParser(
        description="Descarga el fichero completo de HGNC (hgnc_complete_set)."
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Ruta al fichero YAML de configuración (por ejemplo, data_config.yaml).",
    )
    return parser.parse_args()


def main() -> None:
    """
    Punto de entrada principal del script. Carga la configuración,
    establece el logging y ejecuta la descarga del fichero de HGNC.
    """
    args = parse_args()
    configure_logging()

    app_config: AppConfig = load_app_config(args.config)
    download_hgnc_complete_set(app_config.hgnc)


if __name__ == "__main__":
    main()
