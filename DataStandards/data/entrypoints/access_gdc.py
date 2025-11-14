"""
access_gdc.py

Descarga selectiva de metadatos y datos desde el GDC para el proyecto TCGA-LGG:

1. Manifest tipo GDC Data Transfer Tool para ficheros de expresión.
2. Tabla de metadatos fichero–caso–muestra.
3. Tabla mínima de genes de ejemplo vía /genes.
4. Descarga de N ficheros RNA-seq STAR-Counts vía /data.
5. Extracción automática de la lista de genes (Ensembl IDs) a partir
   de uno de los ficheros descargados.

Requiere:
    - data_config.yaml con sección 'gdc' y 'hgnc'.
    - Dataclasses definidas en config.py.
"""

from __future__ import annotations

import csv
import gzip
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import requests

from DataStandards.data.config import AppConfig, GDCConfig, load_app_config


logger = logging.getLogger(__name__)


@dataclass
class SelectedFile:
    """Representa un fichero seleccionado del manifest para descarga vía /data."""

    file_id: str
    file_name: str


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
    token: Optional[str],
    timeout: int,
    fmt: str = "TSV",
) -> str:
    """
    Lanza una petición POST al endpoint /files del GDC y devuelve la respuesta como texto.

    Parameters
    ----------
    endpoint:
        URL completa del endpoint /files.
    filters:
        Diccionario de filtros en el formato del GDC.
    fields:
        Campos a recuperar, separados por comas.
    page_size:
        Tamaño máximo de página (size).
    token:
        Token de autenticación para datos controlados (o None para datos abiertos).
    timeout:
        Timeout en segundos para la petición HTTP.
    fmt:
        Formato de salida ("TSV" o "JSON").

    Returns
    -------
    str
        Contenido de la respuesta como texto.
    """
    headers: Dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    payload: Dict[str, Any] = {
        "filters": filters,
        "fields": fields,
        "size": page_size,
    }

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
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    logger.info("Fichero escrito: %s", output_path)


def download_manifest(gdc_cfg: GDCConfig, token: Optional[str]) -> None:
    """
    Genera un manifest tipo GDC Data Transfer Tool para ficheros de expresión
    de TCGA-LGG y lo escribe en gdc_cfg.manifest_output.
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


def download_file_metadata(gdc_cfg: GDCConfig, token: Optional[str]) -> None:
    """
    Descarga metadatos fichero–caso–muestra para los ficheros del manifest
    y los escribe en gdc_cfg.file_metadata_output.
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


def fetch_genes_table(gdc_cfg: GDCConfig, token: Optional[str]) -> None:
    """
    Recupera información básica de un conjunto pequeño de genes usando el endpoint /genes.

    Para cada símbolo en gdc_cfg.gene_symbols se consulta /genes filtrando por 'symbol'
    y se escribe una tabla TSV con columnas 'symbol' y 'gene_id'.
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

        hit = hits[0]
        gene_id = hit.get("gene_id", "")
        sym = hit.get("symbol", symbol)
        rows.append(f"{sym}\t{gene_id}")

    output_path = Path(gdc_cfg.genes_output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    logger.info("Tabla de genes escrita en: %s", output_path)


def load_gdc_token(token_path: Optional[str]) -> Optional[str]:
    """
    Carga el token del GDC desde disco si se ha configurado una ruta.
    """
    if not token_path:
        return None

    path = Path(token_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"No se encontró el fichero de token: {path}")

    token = path.read_text(encoding="utf-8").strip()
    logger.info("Token GDC cargado desde: %s", path)
    return token


def select_files_from_manifest(
    manifest_path: Path,
    max_files: int,
) -> List[SelectedFile]:
    """
    Selecciona hasta max_files ficheros del manifest TSV para descarga vía /data.

    Se espera que el manifest tenga al menos las columnas 'id' y 'file_name'.
    Si existe 'file_id', se prioriza como UUID; en su defecto se usa 'id'.
    """
    logger.info("Iniciando selección de ficheros del manifest: %s", manifest_path)
    logger.info("Número máximo de ficheros a seleccionar: %d", max_files)
    
    if max_files <= 0:
        logger.warning("max_files es <= 0, no se seleccionarán ficheros")
        return []

    if not manifest_path.is_file():
        logger.error("No se encontró el manifest: %s", manifest_path)
        raise FileNotFoundError(f"No se encontró el manifest: {manifest_path}")

    selected: List[SelectedFile] = []

    with manifest_path.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        fieldnames = reader.fieldnames or []
        logger.info("Columnas encontradas en el manifest: %s", fieldnames)
        
        if "file_name" not in fieldnames:
            logger.error("El manifest no contiene la columna 'file_name'")
            raise ValueError(
                f"El manifest {manifest_path} no contiene la columna 'file_name'."
            )
        id_field = "file_id" if "file_id" in fieldnames else "id"
        if id_field not in fieldnames:
            logger.error("El manifest no contiene columnas 'file_id' ni 'id'")
            raise ValueError(
                f"El manifest {manifest_path} no contiene columnas 'file_id' ni 'id'."
            )
        
        logger.info("Usando campo '%s' como identificador de fichero", id_field)

        for idx, row in enumerate(reader, 1):
            file_id = row[id_field]
            file_name = row["file_name"]
            if not file_id:
                logger.debug("Fila %d: file_id vacío, omitiendo", idx)
                continue
            selected.append(SelectedFile(file_id=file_id, file_name=file_name))
            logger.debug("Fila %d: Seleccionado %s (%s)", idx, file_name, file_id)
            if len(selected) >= max_files:
                logger.info("Alcanzado el límite de %d ficheros", max_files)
                break

    logger.info(
        "Seleccionados %d ficheros del manifest para descarga vía /data", len(selected)
    )
    return selected


def download_files_via_data_endpoint(
    gdc_cfg: GDCConfig,
    token: Optional[str],
    files_to_download: Sequence[SelectedFile],
) -> List[Path]:
    """
    Descarga una lista de ficheros desde el endpoint /data/{file_id}.

    Parameters
    ----------
    gdc_cfg:
        Configuración GDC, incluida la ruta de salida (rnaseq.output_dir).
    token:
        Token GDC o None.
    files_to_download:
        Secuencia de SelectedFile con UUID y nombre remoto.

    Returns
    -------
    list of Path
        Rutas locales a los ficheros descargados.
    """
    logger.info("Iniciando descarga de ficheros vía endpoint /data")
    logger.info("Número de ficheros a descargar: %d", len(files_to_download))
    
    if not files_to_download:
        logger.info("No hay ficheros seleccionados para descarga; se omite /data.")
        return []

    data_base_url = gdc_cfg.base_url.rstrip("/") + "/data"
    output_dir = Path(gdc_cfg.rnaseq.output_dir).expanduser().resolve()
    logger.info("Directorio de salida: %s", output_dir)
    logger.info("Overwrite existing: %s", gdc_cfg.rnaseq.overwrite_existing)
    logger.info("Decompress downloads: %s", gdc_cfg.rnaseq.decompress_downloads)
    
    output_dir.mkdir(parents=True, exist_ok=True)

    headers: Dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        logger.info("Usando token de autenticación")
    else:
        logger.info("No se está usando token de autenticación")

    downloaded_paths: List[Path] = []

    for idx, sf in enumerate(files_to_download, 1):
        dest_path = output_dir / sf.file_name
        logger.info("Procesando fichero %d/%d: %s", idx, len(files_to_download), sf.file_name)

        if dest_path.exists() and not gdc_cfg.rnaseq.overwrite_existing:
            logger.info("Ya existe %s; se omite descarga.", dest_path)
            downloaded_paths.append(dest_path)
            continue

        url = f"{data_base_url}/{sf.file_id}"
        logger.info("Descargando desde: %s", url)

        try:
            with requests.get(url, headers=headers, stream=True, timeout=gdc_cfg.request_timeout) as r:
                r.raise_for_status()
                file_size = int(r.headers.get('content-length', 0))
                logger.info("Tamaño del fichero: %.2f MB", file_size / (1024 * 1024))
                
                with dest_path.open("wb") as fh:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            fh.write(chunk)

            downloaded_paths.append(dest_path)
            logger.info("Descarga completada: %s", dest_path)

            if gdc_cfg.rnaseq.decompress_downloads and dest_path.suffix == ".gz":
                logger.info("Descomprimiendo fichero...")
                _decompress_gzip_in_place(dest_path)
        except Exception as e:
            logger.error("Error al descargar %s: %s", sf.file_name, e)
            raise

    logger.info("Descarga completada. Total de ficheros descargados: %d", len(downloaded_paths))
    return downloaded_paths


def _decompress_gzip_in_place(gz_path: Path) -> Path:
    """
    Descomprime un fichero .gz en el mismo directorio, generando un fichero sin la extensión .gz.
    """
    target_path = gz_path.with_suffix("")
    logger.info("Descomprimiendo %s -> %s", gz_path, target_path)

    with gzip.open(gz_path, "rb") as src, target_path.open("wb") as dst:
        for chunk in iter(lambda: src.read(8192), b""):
            if not chunk:
                break
            dst.write(chunk)

    logger.info("Descompresión completada: %s", target_path)
    return target_path


def _open_text_maybe_gzip(path: Path) -> Iterable[str]:
    """
    Abre un fichero de texto que puede estar comprimido (.gz) y devuelve un iterable
    de líneas decodificadas en UTF-8.
    """
    if path.suffix == ".gz":
        fh = gzip.open(path, "rt", encoding="utf-8")
    else:
        fh = path.open("r", encoding="utf-8")
    return fh


def extract_gene_ids_from_star_counts(
    counts_file: Path,
    gene_id_column_index: int,
    strip_version: bool,
) -> List[str]:
    """
    Extrae los identificadores de gen (Ensembl IDs) de un fichero STAR-Counts.

    Se asume que los Ensembl IDs están en la columna gene_id_column_index (por defecto 0).
    Se ignoran filas cuyo primer campo no parezca un ID Ensembl (p. ej. cabeceras).
    """
    logger.info("Iniciando extracción de gene IDs desde: %s", counts_file)
    logger.info("Columna de gene_id: %d", gene_id_column_index)
    logger.info("Strip version: %s", strip_version)
    
    if not counts_file.is_file():
        logger.error("No se encontró el fichero de counts: %s", counts_file)
        raise FileNotFoundError(f"No se encontró el fichero de counts: {counts_file}")

    gene_ids: set[tuple[str, str]] = set()

    with _open_text_maybe_gzip(counts_file) as fh:
        reader = csv.reader(fh, delimiter="\t")
        total_rows = 0
        skipped_rows = 0
        
        for row in reader:
            total_rows += 1
            if not row:
                skipped_rows += 1
                continue
            if gene_id_column_index >= len(row):
                skipped_rows += 1
                continue
            raw_id = row[gene_id_column_index].strip()
            if not raw_id:
                skipped_rows += 1
                continue
            # Heurística simple: la mayoría de Ensembl genes empiezan por 'ENSG'
            if not raw_id.upper().startswith("ENSG"):
                skipped_rows += 1
                continue
            clean_id = raw_id.split(".")[0] if strip_version else raw_id
            gene_ids.add((raw_id, clean_id))

    # Ordenamos para tener salida determinista
    sorted_pairs = sorted(gene_ids, key=lambda x: x[0])

    logger.info("Total de filas procesadas: %d", total_rows)
    logger.info("Filas omitidas: %d", skipped_rows)
    logger.info("Genes únicos extraídos: %d", len(sorted_pairs))
    
    return [f"{raw}\t{clean}" for raw, clean in sorted_pairs]


def build_gene_table_from_counts(
    gdc_cfg: GDCConfig,
    downloaded_files: Sequence[Path],
) -> Optional[Path]:
    """
    Construye la tabla de genes del proyecto (gdc_genes_tcga_lgg.tsv) a partir de
    uno de los ficheros STAR-Counts descargados.

    Usa el primer fichero de downloaded_files como referencia.
    """
    logger.info("Iniciando construcción de tabla de genes del proyecto")
    logger.info("Número de ficheros descargados disponibles: %d", len(downloaded_files))
    
    if not downloaded_files:
        logger.warning(
            "No hay ficheros descargados de STAR-Counts; se omite construcción de tabla de genes."
        )
        return None

    counts_file = downloaded_files[0]
    logger.info("Usando como referencia el fichero: %s", counts_file)
    
    try:
        lines = extract_gene_ids_from_star_counts(
            counts_file=counts_file,
            gene_id_column_index=gdc_cfg.rnaseq.gene_id_column_index,
            strip_version=gdc_cfg.rnaseq.strip_version,
        )
    except Exception as e:
        logger.error("Error al extraer gene IDs: %s", e)
        raise

    output_path = Path(gdc_cfg.rnaseq.gene_table_output).expanduser().resolve()
    logger.info("Ruta de salida de la tabla de genes: %s", output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    header = "ensembl_gene_id_gdc\tensembl_gene_id"
    content = "\n".join([header] + lines) + "\n"
    output_path.write_text(content, encoding="utf-8")

    logger.info("Tabla de genes del proyecto escrita en: %s", output_path)
    logger.info("Total de genes en la tabla: %d", len(lines))
    return output_path


def run_rnaseq_download_and_gene_extraction(
    gdc_cfg: GDCConfig,
    token: Optional[str],
) -> None:
    """
    Orquesta la selección de ficheros STAR-Counts, descarga vía /data y
    construcción de la tabla de genes del proyecto.
    """
    logger.info("=" * 80)
    logger.info("INICIANDO PROCESO DE DESCARGA RNA-SEQ Y EXTRACCIÓN DE GENES")
    logger.info("=" * 80)
    
    logger.info("Verificando configuración RNA-seq...")
    logger.info("  download_enabled: %s", gdc_cfg.rnaseq.download_enabled)
    logger.info("  max_files: %d", gdc_cfg.rnaseq.max_files)
    logger.info("  output_dir: %s", gdc_cfg.rnaseq.output_dir)
    logger.info("  overwrite_existing: %s", gdc_cfg.rnaseq.overwrite_existing)
    logger.info("  decompress_downloads: %s", gdc_cfg.rnaseq.decompress_downloads)
    logger.info("  gene_table_output: %s", gdc_cfg.rnaseq.gene_table_output)
    
    if not gdc_cfg.rnaseq.download_enabled:
        logger.info("Descarga RNA-seq deshabilitada en la configuración; se omite.")
        logger.info("=" * 80)
        return

    manifest_path = Path(gdc_cfg.manifest_output).expanduser().resolve()
    logger.info("Ruta del manifest: %s", manifest_path)
    logger.info("Manifest existe: %s", manifest_path.exists())
    
    try:
        selected_files = select_files_from_manifest(
            manifest_path=manifest_path,
            max_files=gdc_cfg.rnaseq.max_files,
        )
    except Exception as e:
        logger.error("Error al seleccionar ficheros del manifest: %s", e)
        logger.info("=" * 80)
        raise

    if not selected_files:
        logger.warning(
            "No se seleccionaron ficheros del manifest para descarga RNA-seq; se omite."
        )
        logger.info("=" * 80)
        return

    try:
        downloaded_paths = download_files_via_data_endpoint(
            gdc_cfg=gdc_cfg,
            token=token,
            files_to_download=selected_files,
        )
    except Exception as e:
        logger.error("Error durante la descarga de ficheros: %s", e)
        logger.info("=" * 80)
        raise

    if not downloaded_paths:
        logger.warning(
            "No se descargaron ficheros RNA-seq; no se puede construir la tabla de genes."
        )
        logger.info("=" * 80)
        return

    try:
        build_gene_table_from_counts(gdc_cfg, downloaded_paths)
    except Exception as e:
        logger.error("Error al construir la tabla de genes: %s", e)
        logger.info("=" * 80)
        raise
    
    logger.info("=" * 80)
    logger.info("PROCESO DE DESCARGA RNA-SEQ COMPLETADO EXITOSAMENTE")
    logger.info("=" * 80)


def main(config_path: str = "data_config.yaml") -> None:
    """
    Punto de entrada principal del script.

    - Carga la configuración YAML.
    - Descarga el manifest de expresión para TCGA-LGG.
    - Descarga la tabla de metadatos fichero–caso–muestra.
    - Descarga la tabla mínima de genes vía /genes (opcional).
    - Descarga N ficheros STAR-Counts vía /data.
    - Construye la tabla de genes del proyecto a partir de un fichero STAR-Counts.
    """
    setup_logging()
    logger.info("Cargando configuración desde: %s", config_path)

    app_cfg: AppConfig = load_app_config(Path(config_path))
    gdc_cfg: GDCConfig = app_cfg.gdc

    token = load_gdc_token(gdc_cfg.token_path)

    logger.info("Paso 1/4: Descargando manifest...")
    download_manifest(gdc_cfg, token)
    
    logger.info("Paso 2/4: Descargando metadatos de ficheros...")
    download_file_metadata(gdc_cfg, token)
    
    logger.info("Paso 3/4: Descargando tabla de genes vía /genes...")
    fetch_genes_table(gdc_cfg, token)
    
    logger.info("Paso 4/4: Ejecutando descarga RNA-seq y extracción de genes...")
    try:
        run_rnaseq_download_and_gene_extraction(gdc_cfg, token)
    except Exception as e:
        logger.error("Error en descarga RNA-seq: %s", e, exc_info=True)
        raise


if __name__ == "__main__":
    main()
