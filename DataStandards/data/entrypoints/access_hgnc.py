"""
Script para descargar de forma programática el fichero completo de HGNC
(hgnc_complete_set.txt) usando la URL pública proporcionada por HGNC.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import requests

from DataStandards.data.config import AppConfig, HGNCConfig, load_app_config

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
    """
    url = config.url
    output_path = Path(config.output_path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Descargando conjunto completo de HGNC desde %s", url)
    response = requests.get(url, stream=True, timeout=config.request_timeout)
    response.raise_for_status()

    with output_path.open("wb") as fh:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                fh.write(chunk)

    logger.info("Fichero HGNC guardado en %s", output_path)
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
