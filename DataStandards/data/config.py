"""
Módulo para cargar la configuración de acceso a datos desde un fichero YAML
y exponerla como dataclasses tipadas.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class GDCConfig:
    base_url: str
    project_id: str
    data_category: str
    data_type: str
    workflow_type: str
    fields: str
    manifest_output: str
    file_metadata_fields: str
    file_metadata_output: str
    gene_symbols: list[str]
    genes_output: str
    page_size: int = 10000
    token_path: str | None = None
    request_timeout: int = 120


@dataclass
class HGNCConfig:
    """Configuración específica para descarga del conjunto completo de HGNC."""

    url: str
    output_path: str
    request_timeout: int = 60


@dataclass
class UniProtConfig:
    """Configuración específica para descarga de datos de UniProt."""

    url: str
    query: str
    format: str
    fields: str
    output_path: str
    request_timeout: int = 300


@dataclass
class AppConfig:
    """Configuración completa de la aplicación, incluyendo GDC, HGNC y UniProt."""

    gdc: GDCConfig
    hgnc: HGNCConfig
    uniprot: UniProtConfig | None = None


def _load_yaml(path: Path) -> dict:
    """
    Carga un fichero YAML y devuelve su contenido como diccionario.
    """
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_app_config(config_path: str | Path) -> AppConfig:
    """
    Carga la configuración de aplicación desde un fichero YAML y construye
    las dataclasses AppConfig, GDCConfig, HGNCConfig y UniProtConfig.
    """
    path = Path(config_path).expanduser().resolve()
    raw = _load_yaml(path)

    gdc_raw = raw.get("gdc", {})
    hgnc_raw = raw.get("hgnc", {})
    uniprot_raw = raw.get("uniprot", {})

    gdc_cfg = GDCConfig(**gdc_raw)
    hgnc_cfg = HGNCConfig(**hgnc_raw)
    uniprot_cfg = UniProtConfig(**uniprot_raw) if uniprot_raw else None

    return AppConfig(gdc=gdc_cfg, hgnc=hgnc_cfg, uniprot=uniprot_cfg)
