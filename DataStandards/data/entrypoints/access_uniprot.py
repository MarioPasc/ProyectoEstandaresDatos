#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
access_uniprot.py

Script para obtener información de UniProt relevante para los genes de un
proyecto GDC, usando HGNC como puente.

Flujo:
    1) Leer la tabla de genes del proyecto GDC (gdc.gene_table_output).
    2) Leer hgnc.output_path y seleccionar:
          - genes cuyo ensembl_gene_id esté en el proyecto,
          - locus_type == "protein-coding gene",
          - con uniprot_ids no vacíos.
       → Generar un fichero de mapeo gen–proteína (Ensembl, HGNC, UniProt).
    3) Extraer la lista de UniProt accessions únicas.
    4) Consultar la REST API de UniProt (uniprot.base_url) en lotes,
       obteniendo los campos definidos en uniprot.fields (TSV).
    5) Escribir un TSV con la anotación proteica para esos accesos.

Requisitos:
    - requests
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import requests

from DataStandards.data.config import AppConfig, UniProtConfig, load_app_config


class UniProtAPIError(RuntimeError):
    """Error específico para problemas al acceder a la API de UniProt."""
    pass


# ---------------------------------------------------------------------------
# Utilidades generales
# ---------------------------------------------------------------------------

def setup_logging() -> None:
    """Configura logging básico para el script."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )


def chunked(seq: Sequence[str], size: int) -> Iterable[List[str]]:
    """Genera trozos (chunks) de una secuencia de longitud size."""
    for i in range(0, len(seq), size):
        yield list(seq[i : i + size])


# ---------------------------------------------------------------------------
# Carga y filtrado de GDC / HGNC
# ---------------------------------------------------------------------------

def load_project_ensembl_ids(project_genes_path: Path) -> Set[str]:
    """
    Carga los Ensembl gene IDs del proyecto GDC desde gdc_genes_tcga_lgg.tsv.

    Se asume un TSV con cabecera:
        ensembl_gene_id_gdc    ensembl_gene_id
    """
    logger = logging.getLogger("load_project_ensembl_ids")

    if not project_genes_path.is_file():
        raise FileNotFoundError(
            f"No se encontró el fichero de genes del proyecto: {project_genes_path}"
        )

    ensembl_ids: Set[str] = set()

    with project_genes_path.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        if "ensembl_gene_id" not in (reader.fieldnames or []):
            raise ValueError(
                f"El fichero {project_genes_path} no contiene la columna 'ensembl_gene_id'."
            )

        for row in reader:
            eid = (row.get("ensembl_gene_id") or "").strip()
            if eid:
                ensembl_ids.add(eid)

    logger.info("Ensembl IDs del proyecto cargados: %d", len(ensembl_ids))
    return ensembl_ids


def parse_uniprot_ids_field(value: str) -> List[str]:
    """
    Parsea el campo uniprot_ids de HGNC en una lista de accesos.

    HGNC usa habitualmente '|' como separador; aquí además se eliminan
    espacios en blanco y entradas vacías.
    """
    if not value:
        return []
    parts = [p.strip() for p in value.split("|")]
    return [p for p in parts if p]


def extract_project_uniprot_ids(
    project_ensembl_ids: Set[str],
    hgnc_path: Path,
    mapping_output_path: Path,
    max_accessions: Optional[int],
) -> Tuple[List[str], int]:
    """
    Extrae los UniProt IDs de los genes del proyecto a partir de HGNC.

    Filtro:
        - ensembl_gene_id ∈ project_ensembl_ids
        - locus_type == "protein-coding gene"
        - uniprot_ids no vacío

    Devuelve:
        - lista de accesos UniProt únicos (ordenados)
        - número de filas escritas en el fichero de mapeo
    """
    logger = logging.getLogger("extract_project_uniprot_ids")

    if not hgnc_path.is_file():
        raise FileNotFoundError(f"No se encontró el fichero HGNC: {hgnc_path}")

    mapping_output_path.parent.mkdir(parents=True, exist_ok=True)

    unique_accessions: Set[str] = set()
    n_rows_mapping = 0

    with hgnc_path.open("r", encoding="utf-8") as fh_in, \
            mapping_output_path.open("w", encoding="utf-8", newline="") as fh_out:

        reader = csv.DictReader(fh_in, delimiter="\t")
        fieldnames = reader.fieldnames or []

        required_columns = [
            "ensembl_gene_id",
            "hgnc_id",
            "symbol",
            "locus_type",
            "uniprot_ids",
        ]
        for col in required_columns:
            if col not in fieldnames:
                raise ValueError(
                    f"El fichero HGNC {hgnc_path} no contiene la columna requerida '{col}'."
                )

        writer = csv.writer(fh_out, delimiter="\t")
        writer.writerow(["ensembl_gene_id", "hgnc_id", "symbol", "uniprot_id"])

        for row in reader:
            ensembl_id = (row.get("ensembl_gene_id") or "").strip()
            if not ensembl_id or ensembl_id not in project_ensembl_ids:
                continue

            locus_type = (row.get("locus_type") or "").strip()
            if locus_type != "protein-coding gene":
                continue

            uniprot_field = (row.get("uniprot_ids") or "").strip()
            if not uniprot_field:
                continue

            hgnc_id = (row.get("hgnc_id") or "").strip()
            symbol = (row.get("symbol") or "").strip()

            for acc in parse_uniprot_ids_field(uniprot_field):
                if max_accessions is not None and len(unique_accessions) >= max_accessions:
                    break
                unique_accessions.add(acc)
                writer.writerow([ensembl_id, hgnc_id, symbol, acc])
                n_rows_mapping += 1

            if max_accessions is not None and len(unique_accessions) >= max_accessions:
                logger.info(
                    "Se alcanzó el máximo configurado de accesos UniProt (%d); "
                    "se detiene la lectura HGNC.",
                    max_accessions,
                )
                break

    accessions_sorted = sorted(unique_accessions)
    logger.info(
        "Accesos UniProt únicos seleccionados para el proyecto: %d (filas de mapeo: %d)",
        len(accessions_sorted),
        n_rows_mapping,
    )
    logger.info("Fichero de mapeo escrito en: %s", mapping_output_path)

    return accessions_sorted, n_rows_mapping


# ---------------------------------------------------------------------------
# Cliente UniProt REST API
# ---------------------------------------------------------------------------

def build_uniprot_query(accessions: Sequence[str], cfg: UniProtConfig) -> str:
    """
    Construye la query de UniProt a partir de una lista de accesos y la
    configuración (organism_id, reviewed_only).
    """
    accession_terms = [f"accession:{acc}" for acc in accessions]
    acc_clause = "(" + " OR ".join(accession_terms) + ")"
    org_clause = f"organism_id:{cfg.organism_id}"
    clauses = [acc_clause, org_clause]
    if cfg.reviewed_only:
        clauses.append("reviewed:true")
    return " AND ".join(clauses)


def fetch_uniprot_batch(
    cfg: UniProtConfig,
    accessions: Sequence[str],
    session: Optional[requests.Session] = None,
) -> str:
    """
    Lanza una petición a la API /uniprotkb/search para un conjunto de accesos.

    Devuelve el contenido de la respuesta en formato TSV (texto).
    """
    logger = logging.getLogger("fetch_uniprot_batch")

    if not accessions:
        return ""

    query = build_uniprot_query(accessions, cfg)

    params = {
        "query": query,
        "fields": cfg.fields,
        "format": "tsv",
        "size": str(len(accessions)),
    }

    headers = {
        "User-Agent": "EstandaresDatos-UniProtClient/1.0 (contact: your-email@example.com)"
    }

    sess = session or requests.Session()

    for attempt in range(1, cfg.max_retries + 1):
        try:
            response = sess.get(
                cfg.base_url,
                params=params,
                headers=headers,
                timeout=cfg.timeout,
            )
            if response.status_code == 200:
                return response.text

            if response.status_code in (429, 503):
                logger.warning(
                    "Respuesta %s de UniProt (intento %d/%d). Mensaje: %s",
                    response.status_code,
                    attempt,
                    cfg.max_retries,
                    response.text,
                )
                if attempt < cfg.max_retries:
                    time.sleep(cfg.sleep_between * attempt)
                    continue

            raise UniProtAPIError(
                f"Error al consultar UniProt (HTTP {response.status_code}): {response.text}"
            )

        except (requests.ConnectionError, requests.Timeout) as exc:
            logger.warning(
                "Error de conexión/timeout con UniProt en intento %d/%d: %s",
                attempt,
                cfg.max_retries,
                exc,
            )
            if attempt < cfg.max_retries:
                time.sleep(cfg.sleep_between * attempt)
                continue
            raise UniProtAPIError(f"Error persistente al conectar con UniProt: {exc}") from exc

    raise UniProtAPIError("No se pudo obtener respuesta válida de UniProt tras varios reintentos.")


def download_uniprot_metadata(
    cfg: UniProtConfig,
    accessions: Sequence[str],
) -> None:
    """
    Descarga anotación UniProt para una lista de accesos y la guarda en un TSV.
    """
    logger = logging.getLogger("download_uniprot_metadata")

    if not accessions:
        logger.warning("Lista de accesos UniProt vacía; se omite la descarga de anotación.")
        return

    output_path = Path(cfg.metadata_output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Archivo de salida: %s", output_path)
    logger.info(
        "Descargando metadatos para %d accesos UniProt en lotes de %d...",
        len(accessions),
        cfg.batch_size
    )

    header_written = False
    n_rows_total = 0
    n_batches = (len(accessions) + cfg.batch_size - 1) // cfg.batch_size

    with output_path.open("w", encoding="utf-8", newline="") as fh_out:
        session = requests.Session()

        for i, batch in enumerate(chunked(accessions, cfg.batch_size), start=1):
            logger.info(
                "Procesando lote %d/%d (tamaño: %d accesos)...",
                i,
                n_batches,
                len(batch)
            )

            tsv_text = fetch_uniprot_batch(cfg, batch, session=session)
            if not tsv_text:
                logger.warning("Lote %d/%d no devolvió datos", i, n_batches)
                continue

            lines = tsv_text.splitlines()
            if not lines:
                continue

            if not header_written:
                fh_out.write(lines[0] + "\n")
                header_written = True
                logger.debug("Cabecera escrita: %s", lines[0][:100])

            batch_rows = 0
            for line in lines[1:]:
                if line.strip():
                    fh_out.write(line + "\n")
                    n_rows_total += 1
                    batch_rows += 1

            logger.info("Lote %d/%d completado: %d filas descargadas", i, n_batches, batch_rows)
            time.sleep(cfg.sleep_between)

    logger.info(
        "✓ Descarga de anotación UniProt completada exitosamente"
    )
    logger.info("  - Total de filas: %d", n_rows_total)
    logger.info("  - Archivo guardado: %s", output_path)


# ---------------------------------------------------------------------------
# Orquestación
# ---------------------------------------------------------------------------

def run(app_cfg: AppConfig) -> None:
    """
    Orquesta el flujo completo de obtención de datos de UniProt para el
    proyecto configurado en GDC, usando HGNC como puente.
    """
    logger = logging.getLogger("run")

    if app_cfg.uniprot is None:
        logger.error("No hay configuración 'uniprot' en el fichero YAML.")
        return

    uni_cfg = app_cfg.uniprot
    if not uni_cfg.enabled:
        logger.info("Módulo UniProt deshabilitado en la configuración; se omite.")
        return

    logger.info("Iniciando proceso de descarga de datos UniProt...")

    # Entradas: genes del proyecto GDC y tabla completa de HGNC
    project_genes_path = Path(app_cfg.gdc.rnaseq.gene_table_output).expanduser().resolve()
    hgnc_path = Path(app_cfg.hgnc.output_path).expanduser().resolve()

    mapping_output_path = Path(uni_cfg.mapping_output).expanduser().resolve()

    # Verificar que existan los archivos necesarios
    if not project_genes_path.is_file():
        logger.error(
            "No se encontró el fichero de genes del proyecto GDC: %s",
            project_genes_path
        )
        logger.error(
            "Este archivo se genera al ejecutar: "
            "datastandards-download --config <config> --source gdc"
        )
        raise FileNotFoundError(
            f"Archivo requerido no encontrado: {project_genes_path}\n"
            f"Ejecute primero: datastandards-download --config <config> --source gdc"
        )
    
    if not hgnc_path.is_file():
        logger.error(
            "No se encontró el fichero de datos HGNC: %s",
            hgnc_path
        )
        logger.error(
            "Este archivo se genera al ejecutar: "
            "datastandards-download --config <config> --source hgnc"
        )
        raise FileNotFoundError(
            f"Archivo requerido no encontrado: {hgnc_path}\n"
            f"Ejecute primero: datastandards-download --config <config> --source hgnc"
        )

    logger.info("Cargando genes del proyecto GDC desde: %s", project_genes_path)
    project_ids = load_project_ensembl_ids(project_genes_path)

    logger.info("Extrayendo accesos UniProt desde HGNC: %s", hgnc_path)
    accessions, n_rows_mapping = extract_project_uniprot_ids(
        project_ensembl_ids=project_ids,
        hgnc_path=hgnc_path,
        mapping_output_path=mapping_output_path,
        max_accessions=uni_cfg.max_accessions,
    )

    if not accessions:
        logger.warning("No se obtuvieron accesos UniProt para el proyecto; nada que descargar.")
        return

    logger.info(
        "Número de accesos UniProt seleccionados para anotación: %d (mapeos: %d).",
        len(accessions),
        n_rows_mapping,
    )

    logger.info("Iniciando descarga de metadatos de UniProt...")
    download_uniprot_metadata(uni_cfg, accessions)
    logger.info("Proceso de descarga de UniProt completado exitosamente.")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """
    Parseo de argumentos de línea de comandos.

    De momento solo se expone la ruta al fichero de configuración YAML,
    para mantener toda la parametrización en data_config.yaml.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Descarga anotación UniProt relevante para los genes de un proyecto GDC "
            "usando HGNC como puente, según la configuración definida en data_config.yaml."
        )
    )

    parser.add_argument(
        "--config",
        type=str,
        default="data_config.yaml",
        help="Ruta al fichero YAML de configuración (por defecto: data_config.yaml).",
    )

    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    """Punto de entrada principal del script."""
    setup_logging()
    args = parse_args(argv)

    cfg_path = Path(args.config).expanduser().resolve()
    app_cfg = load_app_config(cfg_path)

    run(app_cfg)


if __name__ == "__main__":
    main(sys.argv[1:])
