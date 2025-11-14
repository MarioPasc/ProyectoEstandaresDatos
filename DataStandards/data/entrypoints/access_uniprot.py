"""
Script para descargar datos de UniProt de forma programática utilizando
la API REST de UniProt.

UniProt proporciona una API REST para consultar y descargar datos de proteínas.
Este script permite descargar proteínas según un query específico en formato TSV.
"""

from __future__ import annotations

import logging
from pathlib import Path

import requests

from DataStandards.data.config import AppConfig, UniProtConfig, load_app_config

logger = logging.getLogger(__name__)


def configure_logging(level: int = logging.INFO) -> None:
    """
    Configura el sistema de logging básico para el script.
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def download_uniprot_data(config: UniProtConfig) -> Path:
    """
    Descarga datos de UniProt según la configuración especificada.

    Parameters
    ----------
    config : UniProtConfig
        Configuración con los parámetros de consulta y descarga.

    Returns
    -------
    Path
        Ruta del fichero descargado.

    Notes
    -----
    La API de UniProt permite consultas con sintaxis específica:
    - organism_id:9606 (humanos)
    - reviewed:true (Swiss-Prot, curado manualmente)
    - gene:TP53 (gen específico)
    
    Ejemplos de queries:
    - "organism_id:9606 AND reviewed:true" : Proteínas humanas revisadas
    - "gene:TP53 AND organism_id:9606" : Proteína TP53 humana
    - "keyword:Cancer AND organism_id:9606" : Proteínas relacionadas con cáncer
    """
    output_path = Path(config.output_path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Construir parámetros de la petición
    params = {
        "query": config.query,
        "format": config.format,
    }
    
    # Añadir campos si están especificados
    if config.fields:
        params["fields"] = config.fields

    logger.info("Descargando datos de UniProt con query: %s", config.query)
    logger.info("Campos solicitados: %s", config.fields)
    logger.info("Formato: %s", config.format)

    try:
        response = requests.get(
            config.url,
            params=params,
            stream=True,
            timeout=config.request_timeout,
        )
        response.raise_for_status()

        # Escribir la respuesta en el fichero
        with output_path.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    fh.write(chunk)

        logger.info("Datos de UniProt guardados en: %s", output_path)
        
        # Mostrar estadísticas básicas
        file_size = output_path.stat().st_size
        logger.info(f"Tamaño del fichero: {file_size / 1024:.2f} KB")
        
        return output_path

    except requests.exceptions.Timeout:
        logger.error("La petición a UniProt ha excedido el tiempo límite")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"Error al realizar la petición a UniProt: {e}")
        raise
    except IOError as e:
        logger.error(f"Error al escribir el fichero: {e}")
        raise


def main(config_path: str = "config/data_config.yaml") -> None:
    """
    Punto de entrada principal del script.

    Parameters
    ----------
    config_path : str
        Ruta al fichero de configuración YAML.
    """
    configure_logging()
    logger.info("Cargando configuración desde: %s", config_path)

    try:
        app_config: AppConfig = load_app_config(Path(config_path))
        
        if app_config.uniprot is None:
            logger.error("No se encontró configuración de UniProt en el fichero de configuración")
            return
        
        download_uniprot_data(app_config.uniprot)
        logger.info("Descarga de UniProt completada exitosamente")
        
    except Exception as e:
        logger.error(f"Error durante la ejecución: {e}")
        raise


if __name__ == "__main__":
    main()
