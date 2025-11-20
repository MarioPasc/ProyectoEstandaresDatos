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
    overwrite_existing: bool = False
    decompress_downloads: bool = False
    gene_id_column_index: int = 0
    strip_version: bool = True


@dataclass
class GDCConfig:
    """Configuración específica para acceso al GDC.

    Multi-project support: project_ids is a list of project IDs to download.
    Output files will be organized in: {base_output_dir}/{project_id}/
    """

    base_url: str
    project_ids: List[str]  # Changed from project_id to support multiple projects
    data_category: str
    data_type: str
    workflow_type: str

    # Base output directory for all GDC data
    # Project-specific subdirectories will be created as: {base_output_dir}/{project_id}/
    base_output_dir: str

    # Manifest /files
    fields: str

    # Metadatos fichero–caso–muestra
    file_metadata_fields: str

    # Tabla de genes de ejemplo vía /genes
    gene_symbols: List[str]

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
    """Configuración específica para descarga de datos de UniProt.

    Multi-project support: UniProt data will be organized per-project in:
    {base_output_dir}/{project_id}/
    """

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

    # Base output directory for UniProt data
    # Project-specific subdirectories will be created as: {base_output_dir}/{project_id}/
    base_output_dir: str = "data/uniprot"

@dataclass
class MongoDBConfig:
    """Configuración de conexión a MongoDB."""

    mongo_uri: str = "mongodb://localhost:27017/"
    database_name: str = "estandares_db"
    collection_name: str = "gdc_cases"


@dataclass
class ProjectMetadata:
    """Metadata para un proyecto GDC individual."""

    project_id: str
    disease_type: str
    primary_site: str
    data_category: str


@dataclass
class GDCMongoDataConfig:
    """Configuración de rutas de datos GDC para importación a MongoDB.

    Multi-project support: Configuration for importing multiple GDC projects
    into a single MongoDB document with a projects array structure.
    """

    # Base directory where project-specific data folders are located
    base_data_dir: str

    # List of projects to import with their metadata
    projects: List[ProjectMetadata]

    # Filename patterns (relative to {base_data_dir}/{project_id}/)
    manifest_filename: str = "gdc_manifest_{project_id_lower}.tsv"
    metadata_filename: str = "gdc_file_metadata_{project_id_lower}.tsv"
    genes_filename: str = "gdc_genes_{project_id_lower}.tsv"
    star_counts_dirname: str = "star_counts"


@dataclass
class GDCMongoOptionsConfig:
    """Opciones de procesamiento para la importación GDC a MongoDB."""

    drop_collection: bool = False
    process_expression: bool = True
    max_files_to_process: Optional[int] = None
    verbose: bool = True
    save_as_json_gdc: Optional[str] = None
    save_as_json_hgnc: Optional[str] = None


@dataclass
class GDCMongoAppConfig:
    """Configuración completa para importación GDC a MongoDB."""

    mongodb: MongoDBConfig
    gdc: GDCMongoDataConfig
    options: GDCMongoOptionsConfig = field(default_factory=GDCMongoOptionsConfig)


@dataclass
class UniProtProjectMetadata:
    """Metadata para un proyecto UniProt individual."""

    project_id: str


@dataclass
class UniProtMongoDataConfig:
    """Configuración de rutas de datos UniProt para importación a MongoDB.

    Multi-project support: Configuration for importing multiple UniProt projects
    into a single MongoDB document with uniprot_entries array structure.
    """

    # Base directory where project-specific data folders are located
    base_data_dir: str

    # List of projects to import
    projects: List[UniProtProjectMetadata]

    # Filename patterns (relative to {base_data_dir}/{project_id}/)
    mapping_filename: str = "uniprot_mapping_{project_id_lower}.tsv"
    metadata_filename: str = "uniprot_metadata_{project_id_lower}.tsv"


@dataclass
class UniProtMongoOptionsConfig:
    """Opciones de procesamiento para la importación UniProt a MongoDB."""

    drop_collection: bool = False
    verbose: bool = True
    save_as_json: Optional[str] = None
    no_insert_mongo: bool = False  # Only generate JSON, don't insert to MongoDB


@dataclass
class UniProtMongoAppConfig:
    """Configuración completa para importación UniProt a MongoDB."""

    mongodb: MongoDBConfig
    uniprot: UniProtMongoDataConfig
    options: UniProtMongoOptionsConfig = field(default_factory=UniProtMongoOptionsConfig)


@dataclass
class HGNCMongoConfig:
    """Configuración de datos HGNC para importación a MongoDB.

    Contiene las rutas y configuración necesaria para importar datos HGNC
    combinados con datos de expresión de GDC.
    """

    # Path to HGNC complete set TSV file
    hgnc_tsv_path: str

    # MongoDB collection name for HGNC data
    collection_name: str = "hgnc_genes"


@dataclass
class HGNCMongoOptionsConfig:
    """Opciones de procesamiento para la importación HGNC a MongoDB."""

    drop_collection: bool = False
    verbose: bool = True
    save_as_json_hgnc: Optional[str] = None


@dataclass
class HGNCMongoAppConfig:
    """Configuración completa para importación HGNC a MongoDB."""

    mongodb: MongoDBConfig
    hgnc: HGNCMongoConfig
    gdc: GDCMongoDataConfig
    options: HGNCMongoOptionsConfig = field(default_factory=HGNCMongoOptionsConfig)


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

    Multi-project support: Expects project_ids as a list in the YAML config.
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
        project_ids=gdc_raw["project_ids"],  # Changed to project_ids (list)
        data_category=gdc_raw["data_category"],
        data_type=gdc_raw["data_type"],
        workflow_type=gdc_raw["workflow_type"],
        base_output_dir=gdc_raw["base_output_dir"],  # Changed to base_output_dir
        fields=gdc_raw["fields"],
        file_metadata_fields=gdc_raw["file_metadata_fields"],
        gene_symbols=gdc_raw.get("gene_symbols", []),
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


def load_gdc_mongo_config(config_path: str | Path) -> GDCMongoAppConfig:
    """
    Carga la configuración de importación GDC a MongoDB desde un fichero YAML
    y construye las dataclasses correspondientes.

    Multi-project support: Parses projects list from YAML and creates
    ProjectMetadata objects for each project.
    """
    path = Path(config_path).expanduser().resolve()
    raw: Dict[str, Any] = _load_yaml(path)

    # Cargar configuración MongoDB
    mongodb_raw: Dict[str, Any] = raw.get("mongodb", {})
    mongodb_cfg = MongoDBConfig(**mongodb_raw)

    # Cargar configuración de datos GDC
    gdc_raw: Dict[str, Any] = raw.get("gdc", {})

    # Parse projects list
    projects_raw: List[Dict[str, Any]] = gdc_raw.get("projects", [])
    projects = [ProjectMetadata(**proj) for proj in projects_raw]

    # Create GDCMongoDataConfig with parsed projects
    gdc_cfg = GDCMongoDataConfig(
        base_data_dir=gdc_raw["base_data_dir"],
        projects=projects,
        manifest_filename=gdc_raw.get("manifest_filename", "gdc_manifest_{project_id_lower}.tsv"),
        metadata_filename=gdc_raw.get("metadata_filename", "gdc_file_metadata_{project_id_lower}.tsv"),
        genes_filename=gdc_raw.get("genes_filename", "gdc_genes_{project_id_lower}.tsv"),
        star_counts_dirname=gdc_raw.get("star_counts_dirname", "star_counts"),
    )

    # Cargar opciones
    options_raw: Dict[str, Any] = raw.get("options", {})
    options_cfg = GDCMongoOptionsConfig(**options_raw)

    return GDCMongoAppConfig(mongodb=mongodb_cfg, gdc=gdc_cfg, options=options_cfg)


def load_hgnc_mongo_config(config_path: str | Path) -> HGNCMongoAppConfig:
    """
    Carga la configuración de importación HGNC a MongoDB desde un fichero YAML
    y construye las dataclasses correspondientes.

    Integrates HGNC gene data with GDC expression data for all configured projects.
    """
    path = Path(config_path).expanduser().resolve()
    raw: Dict[str, Any] = _load_yaml(path)

    # Cargar configuración MongoDB
    mongodb_raw: Dict[str, Any] = raw.get("mongodb", {})
    # Override collection_name for UniProt
    mongodb_raw["collection_name"] = "uniprot_entries"
    mongodb_cfg = MongoDBConfig(**mongodb_raw)

    # Cargar configuración de datos UniProt
    uniprot_raw: Dict[str, Any] = raw.get("uniprot", {})

    # Parse projects list
    projects_raw: List[Dict[str, Any]] = uniprot_raw.get("projects", [])
    projects = [UniProtProjectMetadata(**proj) for proj in projects_raw]

    # Create UniProtMongoDataConfig with parsed projects
    uniprot_cfg = UniProtMongoDataConfig(
        base_data_dir=uniprot_raw["base_data_dir"],
        projects=projects,
        mapping_filename=uniprot_raw.get("mapping_filename", "uniprot_mapping_{project_id_lower}.tsv"),
        metadata_filename=uniprot_raw.get("metadata_filename", "uniprot_metadata_{project_id_lower}.tsv"),
    )

    # Cargar opciones (solo las relevantes para UniProt)
    options_raw: Dict[str, Any] = raw.get("options", {})
    # Filter only UniProt-relevant options
    uniprot_options = {
        "drop_collection": options_raw.get("drop_collection", False),
        "verbose": options_raw.get("verbose", True),
        "save_as_json": options_raw.get("save_as_json"),
        "no_insert_mongo": options_raw.get("no_insert_mongo", False),
    }
    options_cfg = UniProtMongoOptionsConfig(**uniprot_options)

    return UniProtMongoAppConfig(mongodb=mongodb_cfg, uniprot=uniprot_cfg, options=options_cfg)

    # Extract hgnc_collection_name before creating MongoDBConfig
    hgnc_collection_name = mongodb_raw.get("hgnc_collection_name", "hgnc_genes")

    # Create MongoDBConfig with only the fields it accepts
    mongodb_cfg = MongoDBConfig(
        mongo_uri=mongodb_raw.get("mongo_uri", "mongodb://localhost:27017/"),
        database_name=mongodb_raw.get("database_name", "estandares_db"),
        collection_name=mongodb_raw.get("collection_name", "gdc_cases")
    )

    # Cargar configuración HGNC
    hgnc_raw: Dict[str, Any] = raw.get("hgnc", {})
    hgnc_cfg = HGNCMongoConfig(
        hgnc_tsv_path=hgnc_raw["output_path"],
        collection_name=hgnc_collection_name
    )

    # Cargar configuración de datos GDC (reutilizamos la misma estructura)
    gdc_raw: Dict[str, Any] = raw.get("gdc", {})

    # Parse projects list
    projects_raw: List[Dict[str, Any]] = gdc_raw.get("projects", [])
    projects = [ProjectMetadata(**proj) for proj in projects_raw]

    # Create GDCMongoDataConfig with parsed projects
    gdc_cfg = GDCMongoDataConfig(
        base_data_dir=gdc_raw["base_data_dir"],
        projects=projects,
        manifest_filename=gdc_raw.get("manifest_filename", "gdc_manifest_{project_id_lower}.tsv"),
        metadata_filename=gdc_raw.get("metadata_filename", "gdc_file_metadata_{project_id_lower}.tsv"),
        genes_filename=gdc_raw.get("genes_filename", "gdc_genes_{project_id_lower}.tsv"),
        star_counts_dirname=gdc_raw.get("star_counts_dirname", "star_counts"),
    )

    # Cargar opciones
    options_raw: Dict[str, Any] = raw.get("options", {})
    hgnc_options_cfg = HGNCMongoOptionsConfig(
        drop_collection=options_raw.get("drop_collection", False),
        verbose=options_raw.get("verbose", True),
        save_as_json_hgnc=options_raw.get("save_as_json_hgnc")
    )

    return HGNCMongoAppConfig(mongodb=mongodb_cfg, hgnc=hgnc_cfg, gdc=gdc_cfg, options=hgnc_options_cfg)
