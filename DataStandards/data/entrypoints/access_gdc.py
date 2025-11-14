"""
access_gdc.py

Descarga selectiva de metadatos desde el GDC para el proyecto TCGA-LGG:

1. Manifest tipo GDC Data Transfer Tool para ficheros de expresión.
2. Tabla de metadatos fichero–caso–muestra para los mismos ficheros.
3. Tabla mínima de genes (symbol ↔ Ensembl gene_id) usando el endpoint /genes.

Requiere:
    - data_config.yaml con sección 'gdc' y dataclasses definidas en data_config.py.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

import requests

from DataStandards.data.config import AppConfig, load_app_config, GDCConfig  


logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Configura el logging básico para el módulo."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )


def build_gdc_files_filters(gdc_cfg: GDCConfig) -> Dict[str, Any]:
    """
    Construye el diccionario de filtros para el endpoint /files del GDC.

    Los filtros restringen:
        - Proyecto (cases.project.project_id)
        - Data Category (data_category)
        - Data Type (data_type)
        - Workflow (analysis.workflow_type), si está configurado.

    Returns
    -------
    dict
        Estructura de filtros según el lenguaje de filtros del GDC API.
    """
    filters: Dict[str, Any] = {
        "op": "and",
        "content": [
            {
                "op": "in",
                "content": {
                    "field": "cases.project.project_id",
                    "value": [gdc_cfg.project_id],
                },
            },
            {
                "op": "in",
                "content": {
                    "field": "data_category",
                    "value": [gdc_cfg.data_category],
                },
            },
            {
                "op": "in",
                "content": {
                    "field": "data_type",
                    "value": [gdc_cfg.data_type],
                },
            },
        ],
    }

    # El workflow_type es opcional, pero reduce mucho el volumen
    if gdc_cfg.workflow_type:
        filters["content"].append(
            {
                "op": "in",
                "content": {
                    "field": "analysis.workflow_type",
                    "value": [gdc_cfg.workflow_type],
                },
            }
        )

    return filters


def _post_gdc_files(
    endpoint: str,
    filters: Dict[str, Any],
    fields: str,
    page_size: int,
    token: str | None,
    timeout: int,
    fmt: str = "TSV",
) -> str:
    """
    Lanza una petición POST al endpoint /files del GDC y devuelve la respuesta completa como texto.

    Parameters
    ----------
    endpoint : str
        URL base del endpoint (normalmente 'https://api.gdc.cancer.gov/files').
    filters : dict
        Diccionario de filtros en el formato del GDC.
    fields : str
        Campos a recuperar, separados por comas.
    page_size : int
        Tamaño máximo de página (size). Para TCGA-LGG + RNA-Seq suele bastar con un único request.
    token : str or None
        Token de autenticación para datos controlados. Si es None, no se añade cabecera Authorization.
    timeout : int
        Timeout en segundos para la petición HTTP.
    fmt : str
        Formato de salida del GDC. Puede ser "TSV" o "JSON". Por defecto "TSV".

    Returns
    -------
    str
        Contenido de la respuesta como texto (TSV o JSON, según fmt).
    """
    headers: Dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    payload: Dict[str, Any] = {
        "filters": filters,
        "fields": fields,
        "size": page_size,
    }

    # El GDC espera 'format' en minúsculas ('tsv' / 'json')
    if fmt.upper() == "TSV":
        payload["format"] = "tsv"
    elif fmt.upper() == "JSON":
        payload["format"] = "json"
    else:
        raise ValueError(f"Formato GDC no soportado: {fmt}")

    logger.info("Llamando a GDC /files con campos: %s", fields)
    response = requests.post(endpoint, json=payload, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.text


def write_text_to_file(content: str, output_path: Path) -> None:
    """
    Escribe un texto en disco creando directorios intermedios si es necesario.

    Parameters
    ----------
    content : str
        Contenido a escribir.
    output_path : Path
        Ruta del fichero de salida.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    logger.info("Fichero escrito: %s", output_path)


def download_manifest(gdc_cfg: GDCConfig, token: str | None) -> None:
    """
    Genera un manifest tipo GDC Data Transfer Tool para ficheros de expresión de TCGA-LGG.

    Outputs
    -------
    - gdc_cfg.manifest_output : TSV con columnas id, filename, md5, size, state.
    """
    files_endpoint = gdc_cfg.base_url.rstrip("/") + "/files"
    filters = build_gdc_files_filters(gdc_cfg)
    content = _post_gdc_files(
        endpoint=files_endpoint,
        filters=filters,
        fields=gdc_cfg.fields,
        page_size=gdc_cfg.page_size,
        token=token,
        timeout=gdc_cfg.request_timeout,
        fmt="TSV",
    )

    write_text_to_file(content, Path(gdc_cfg.manifest_output))


def download_file_metadata(gdc_cfg: GDCConfig, token: str | None) -> None:
    """
    Descarga metadatos fichero–caso–muestra para los mismos ficheros del manifest.

    Outputs
    -------
    - gdc_cfg.file_metadata_output : TSV con columnas definidas en file_metadata_fields.
    """
    files_endpoint = gdc_cfg.base_url.rstrip("/") + "/files"
    filters = build_gdc_files_filters(gdc_cfg)
    content = _post_gdc_files(
        endpoint=files_endpoint,
        filters=filters,
        fields=gdc_cfg.file_metadata_fields,
        page_size=gdc_cfg.page_size,
        token=token,
        timeout=gdc_cfg.request_timeout,
        fmt="TSV",
    )

    write_text_to_file(content, Path(gdc_cfg.file_metadata_output))


def fetch_genes_table(gdc_cfg: GDCConfig, token: str | None) -> None:
    """
    Recupera información básica de un conjunto pequeño de genes usando el endpoint /genes.

    Para cada símbolo en gdc_cfg.gene_symbols se consulta el endpoint /genes con un filtro
    sobre el campo 'symbol' y se extrae el primer hit (gene_id + symbol).

    Outputs
    -------
    - gdc_cfg.genes_output : TSV con cabecera 'symbol<TAB>gene_id'.
    """
    if not gdc_cfg.gene_symbols:
        logger.info("No hay símbolos de gen configurados; se omite /genes.")
        return

    genes_endpoint = gdc_cfg.base_url.rstrip("/") + "/genes"
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    rows: List[str] = ["symbol\tgene_id"]

    for symbol in gdc_cfg.gene_symbols:
        filters = {
            "op": "and",
            "content": [
                {
                    "op": "in",
                    "content": {
                        "field": "symbol",
                        "value": [symbol],
                    },
                }
            ],
        }

        params = {
            "filters": json.dumps(filters),
            "fields": "gene_id,symbol",
            "size": 5,
        }

        logger.info("Consultando /genes para símbolo: %s", symbol)
        response = requests.get(
            genes_endpoint, params=params, headers=headers, timeout=gdc_cfg.request_timeout
        )
        response.raise_for_status()
        data = response.json()

        hits = data.get("data", {}).get("hits", [])
        if not hits:
            logger.warning("Sin resultados para símbolo %s en /genes", symbol)
            continue

        # Tomamos el primer hit como representación del símbolo
        hit = hits[0]
        gene_id = hit.get("gene_id", "")
        sym = hit.get("symbol", symbol)
        rows.append(f"{sym}\t{gene_id}")

    output_path = Path(gdc_cfg.genes_output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    logger.info("Tabla de genes escrita en: %s", output_path)


def load_gdc_token(token_path: str | None) -> str | None:
    """
    Carga el token del GDC desde disco si se ha configurado una ruta.

    Parameters
    ----------
    token_path : str or None
        Ruta al fichero de token o None si no se usa token.

    Returns
    -------
    str or None
        Contenido del token o None.
    """
    if not token_path:
        return None

    path = Path(token_path)
    if not path.is_file():
        raise FileNotFoundError(f"No se encontró el fichero de token: {path}")

    token = path.read_text(encoding="utf-8").strip()
    logger.info("Token GDC cargado desde: %s", path)
    return token


def main(config_path: str = "data_config.yaml") -> None:
    """
    Punto de entrada principal del script.

    - Carga la configuración YAML.
    - Descarga el manifest de expresión para TCGA-LGG.
    - Descarga la tabla de metadatos fichero–caso–muestra.
    - Descarga la tabla mínima de genes para enlazar con HGNC.
    """
    setup_logging()
    logger.info("Cargando configuración desde: %s", config_path)

    app_cfg: AppConfig = load_app_config(Path(config_path))
    gdc_cfg: GDCConfig = app_cfg.gdc

    token = load_gdc_token(gdc_cfg.token_path)

    download_manifest(gdc_cfg, token)
    download_file_metadata(gdc_cfg, token)
    fetch_genes_table(gdc_cfg, token)


if __name__ == "__main__":
    main()
