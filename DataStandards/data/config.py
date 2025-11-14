"""
config.py

Definición de dataclasses para la configuración de acceso a datos (GDC y HGNC)
y carga desde un fichero YAML.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class RnaSeqConfig:
    """Configuración específica para descargas RNA-seq (STAR-Counts) desde GDC."""

    download_enabled: bool = True
    max_files: int = 5
    output_dir: str = "data/gdc/star_counts"
    overwrite_existing: bool = False
    decompress_downloads: bool = False
    gene_table_output: str = "data/gdc_genes_tcga_lgg.tsv"
    gene_id_column_index: int = 0
    strip_version: bool = True


@dataclass
class GDCConfig:
    """Configuración específica para acceso al GDC."""

    base_url: str
    project_id: str
    data_category: str
    data_type: str
    workflow_type: str

    # Manifest /files
    fields: str
    manifest_output: str

    # Metadatos fichero–caso–muestra
    file_metadata_fields: str
    file_metadata_output: str

    # Tabla de genes de ejemplo vía /genes
    gene_symbols: List[str]
    genes_output: str

    # Parámetros generales de la API
    page_size: int = 10000
    token_path: Optional[str] = None
    request_timeout: int = 120

    # Nueva subconfiguración RNA-seq
    rnaseq: RnaSeqConfig = field(default_factory=RnaSeqConfig)


@dataclass
class HGNCConfig:
    """Configuración específica para descarga del conjunto completo de HGNC."""

    url: str
    output_path: str
    request_timeout: int = 60


@dataclass
class UniProtConfig:
    """Configuración específica para descarga de datos de UniProt."""

    # Activación/desactivación del módulo UniProt
    enabled: bool = True

    # Endpoint base de UniProtKB (búsquedas)
    base_url: str = "https://rest.uniprot.org/uniprotkb/search"

    # Parámetros biológicos
    organism_id: int = 9606
    reviewed_only: bool = True

    # Campos a solicitar a UniProt en formato TSV
    fields: str = (
        "accession,id,reviewed,"
        "gene_primary,gene_names,"
        "organism_id,protein_name,length,protein_existence,"
        "go_f,go_p,go_c,"
        "cc_function,cc_subcellular_location"
    )

    # Parámetros de la API
    batch_size: int = 200
    max_retries: int = 3
    timeout: int = 60
    sleep_between: float = 0.34

    # Control del tamaño del dataset (None = sin límite)
    max_accessions: Optional[int] = None

    # Ficheros de salida
    mapping_output: str = "data/uniprot/uniprot_mapping_tcga_lgg.tsv"
    metadata_output: str = "data/uniprot/uniprot_metadata_tcga_lgg.tsv"

@dataclass
class AppConfig:
    """Configuración completa de la aplicación (GDC + HGNC + UniProt)."""

    gdc: GDCConfig
    hgnc: HGNCConfig
    uniprot: Optional[UniProtConfig] = None

def _load_yaml(path: Path) -> Dict[str, Any]:
    """Carga un fichero YAML y devuelve su contenido como diccionario."""
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_app_config(config_path: str | Path) -> AppConfig:
    """
    Carga la configuración de aplicación desde un fichero YAML y construye
    las dataclasses AppConfig, GDCConfig, HGNCConfig, UniProtConfig y RnaSeqConfig.
    """
    path = Path(config_path).expanduser().resolve()
    raw: Dict[str, Any] = _load_yaml(path)

    gdc_raw: Dict[str, Any] = raw.get("gdc", {})
    hgnc_raw: Dict[str, Any] = raw.get("hgnc", {})
    uniprot_raw: Dict[str, Any] = raw.get("uniprot", {})

    rnaseq_raw: Dict[str, Any] = gdc_raw.get("rnaseq", {})
    rnaseq_cfg = RnaSeqConfig(**rnaseq_raw)

    # Extraemos explícitamente las claves de GDC, dejando fuera 'rnaseq'
    gdc_cfg = GDCConfig(
        base_url=gdc_raw["base_url"],
        project_id=gdc_raw["project_id"],
        data_category=gdc_raw["data_category"],
        data_type=gdc_raw["data_type"],
        workflow_type=gdc_raw["workflow_type"],
        fields=gdc_raw["fields"],
        manifest_output=gdc_raw["manifest_output"],
        file_metadata_fields=gdc_raw["file_metadata_fields"],
        file_metadata_output=gdc_raw["file_metadata_output"],
        gene_symbols=gdc_raw.get("gene_symbols", []),
        genes_output=gdc_raw["genes_output"],
        page_size=gdc_raw.get("page_size", 10000),
        token_path=gdc_raw.get("token_path"),
        request_timeout=gdc_raw.get("request_timeout", 120),
        rnaseq=rnaseq_cfg,
    )

    hgnc_cfg = HGNCConfig(
        url=hgnc_raw["url"],
        output_path=hgnc_raw["output_path"],
        request_timeout=hgnc_raw.get("request_timeout", 60),
    )

    uniprot_cfg = UniProtConfig(**uniprot_raw) if uniprot_raw else None

    return AppConfig(gdc=gdc_cfg, hgnc=hgnc_cfg, uniprot=uniprot_cfg)
