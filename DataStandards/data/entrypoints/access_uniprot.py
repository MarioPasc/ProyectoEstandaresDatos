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

    Filtros aplicados:
        - ensembl_gene_id ∈ project_ensembl_ids (considerando valores múltiples separados por '|')
        - locus_group == "protein-coding gene"
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

        # Ahora exigimos locus_group (no solo locus_type)
        required_columns = [
            "ensembl_gene_id",
            "hgnc_id",
            "symbol",
            "locus_group",
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
            # 1) Ensembl IDs del gen (posiblemente múltiples separados por '|')
            ensembl_field = (row.get("ensembl_gene_id") or "").strip()
            if not ensembl_field:
                continue

            row_ensembl_ids = [
                eid.strip()
                for eid in ensembl_field.split("|")
                if eid.strip()
            ]
            # Nos quedamos solo con los Ensembl IDs que están en el proyecto
            matching_ensembl_ids = [
                eid for eid in row_ensembl_ids if eid in project_ensembl_ids
            ]
            if not matching_ensembl_ids:
                continue

            # 2) Filtro de tipo de locus: usar locus_group, no locus_type
            locus_group = (row.get("locus_group") or "").strip()
            if locus_group != "protein-coding gene":
                continue

            locus_group = (row.get("locus_type") or "").strip()
            if locus_group != "gene with protein product":
                continue


            # 3) Campo UniProt
            uniprot_field = (row.get("uniprot_ids") or "").strip()
            if not uniprot_field:
                continue

            hgnc_id = (row.get("hgnc_id") or "").strip()
            symbol = (row.get("symbol") or "").strip()

            uniprot_accessions = parse_uniprot_ids_field(uniprot_field)
            if not uniprot_accessions:
                continue

            for ensembl_id in matching_ensembl_ids:
                for acc in uniprot_accessions:
                    if max_accessions is not None and len(unique_accessions) >= max_accessions:
                        break
                    unique_accessions.add(acc)
                    writer.writerow([ensembl_id, hgnc_id, symbol, acc])
                    n_rows_mapping += 1

                if max_accessions is not None and len(unique_accessions) >= max_accessions:
                    break

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
    output_path: Optional[Path] = None,
) -> None:
    """
    Descarga anotación UniProt para una lista de accesos y la guarda en un TSV.

    Args:
        cfg: Configuración UniProt
        accessions: Lista de accesos UniProt
        output_path: Path de salida opcional (si no se proporciona, usa cfg.base_output_dir)
    """
    logger = logging.getLogger("download_uniprot_metadata")

    if not accessions:
        logger.warning("Lista de accesos UniProt vacía; se omite la descarga de anotación.")
        return

    if output_path is None:
        # Backwards compatibility: use base_output_dir as default
        output_path = Path(cfg.base_output_dir).expanduser().resolve() / "uniprot_metadata.tsv"

    output_path = Path(output_path).expanduser().resolve()
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
    Orquesta el flujo completo de obtención de datos de UniProt para todos
    los proyectos configurados en GDC, usando HGNC como puente.

    Multi-project support: Procesa cada proyecto por separado, creando
    subdirectorios específicos para UniProt data.
    """
    logger = logging.getLogger("run")

    if app_cfg.uniprot is None:
        logger.error("No hay configuración 'uniprot' en el fichero YAML.")
        return

    uni_cfg = app_cfg.uniprot
    if not uni_cfg.enabled:
        logger.info("Módulo UniProt deshabilitado en la configuración; se omite.")
        return

    logger.info("=" * 100)
    logger.info("INICIANDO PROCESO DE DESCARGA UNIPROT PARA %d PROYECTO(S)", len(app_cfg.gdc.project_ids))
    logger.info("Proyectos: %s", ", ".join(app_cfg.gdc.project_ids))
    logger.info("=" * 100)

    # Verificar que existe HGNC
    hgnc_path = Path(app_cfg.hgnc.output_path).expanduser().resolve()
    if not hgnc_path.is_file():
        logger.error("No se encontró el fichero de datos HGNC: %s", hgnc_path)
        logger.error("Este archivo se genera al ejecutar: datastandards-download --config <config> --source hgnc")
        raise FileNotFoundError(
            f"Archivo requerido no encontrado: {hgnc_path}\n"
            f"Ejecute primero: datastandards-download --config <config> --source hgnc"
        )

    # Process each project
    for project_idx, project_id in enumerate(app_cfg.gdc.project_ids, 1):
        logger.info("\n" + "=" * 100)
        logger.info("PROCESANDO UNIPROT PARA PROYECTO %d/%d: %s", project_idx, len(app_cfg.gdc.project_ids), project_id)
        logger.info("=" * 100)

        try:
            # Build project-specific paths
            gdc_base_dir = Path(app_cfg.gdc.base_output_dir).expanduser().resolve()
            project_dir = gdc_base_dir / project_id
            project_id_lower = project_id.lower().replace("-", "_")
            project_genes_path = project_dir / f"gdc_genes_{project_id_lower}.tsv"

            # Build UniProt output paths for this project
            uniprot_base_dir = Path(uni_cfg.base_output_dir).expanduser().resolve()
            uniprot_project_dir = uniprot_base_dir / project_id
            uniprot_project_dir.mkdir(parents=True, exist_ok=True)

            mapping_output_path = uniprot_project_dir / f"uniprot_mapping_{project_id_lower}.tsv"
            metadata_output_path = uniprot_project_dir / f"uniprot_metadata_{project_id_lower}.tsv"

            # Verificar que exista el fichero de genes del proyecto
            if not project_genes_path.is_file():
                logger.error("No se encontró el fichero de genes para proyecto %s: %s", project_id, project_genes_path)
                logger.error("Este archivo se genera al ejecutar: datastandards-download --config <config> --source gdc")
                raise FileNotFoundError(
                    f"Archivo requerido no encontrado: {project_genes_path}\n"
                    f"Ejecute primero: datastandards-download --config <config> --source gdc"
                )

            logger.info("Cargando genes del proyecto %s desde: %s", project_id, project_genes_path)
            project_ensembl_ids = load_project_ensembl_ids(project_genes_path)

            logger.info("Extrayendo accesos UniProt desde HGNC: %s", hgnc_path)
            accessions, n_rows_mapping = extract_project_uniprot_ids(
                project_ensembl_ids=project_ensembl_ids,
                hgnc_path=hgnc_path,
                mapping_output_path=mapping_output_path,
                max_accessions=uni_cfg.max_accessions,
            )

            if not accessions:
                logger.warning("No se obtuvieron accesos UniProt para %s; se omite descarga de metadatos.", project_id)
                continue

            logger.info(
                "Número de accesos UniProt seleccionados para %s: %d (mapeos: %d).",
                project_id,
                len(accessions),
                n_rows_mapping,
            )

            logger.info("Iniciando descarga de metadatos de UniProt para %s...", project_id)
            # Download to project-specific path
            download_uniprot_metadata(uni_cfg, accessions, output_path=metadata_output_path)

            logger.info("✓ Proceso UniProt completado para proyecto %s", project_id)

        except Exception as e:
            logger.error("✗ Error al procesar UniProt para proyecto %s: %s", project_id, e, exc_info=True)
            raise

    logger.info("\n" + "=" * 100)
    logger.info("DESCARGA UNIPROT COMPLETADA PARA TODOS LOS PROYECTOS")
    logger.info("=" * 100)


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
