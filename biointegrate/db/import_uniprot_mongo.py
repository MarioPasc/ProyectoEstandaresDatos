"""
import_uniprot_mongo.py

Importador de datos UniProt a MongoDB.
Construye una colección con estructura multi-proyecto:
  uniprot_entries → [entradas UniProt con información por proyecto]
"""

import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from bson import ObjectId
from pymongo import MongoClient


def _none_if_nan(value):
    """Devuelve None si el valor es NaN (pandas/numpy), en otro caso lo deja igual."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _split_field(value, sep=";"):
    """Divide un campo de TSV en lista, manejando NaN y vacíos."""
    value = _none_if_nan(value)
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    parts = [p.strip() for p in text.split(sep)]
    return [p for p in parts if p]


def _bool_from_reviewed(value) -> bool:
    """Convierte la columna 'reviewed' de UniProt a booleano."""
    value = _none_if_nan(value)
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"reviewed", "true", "yes", "1"}


def load_uniprot_mapping(mapping_path: str) -> pd.DataFrame:
    """
    Carga el fichero de mapping UniProt (TSV).

    Contiene: ensembl_gene_id, hgnc_id, symbol, uniprot_id
    """
    if not Path(mapping_path).exists():
        raise FileNotFoundError(f"Mapping no encontrado: {mapping_path}")

    df = pd.read_csv(mapping_path, sep='\t', dtype=str)
    expected_cols = {"ensembl_gene_id", "hgnc_id", "symbol", "uniprot_id"}
    missing = expected_cols - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas en mapping TSV: {missing}")

    df = df.fillna('')
    return df


def load_uniprot_metadata(metadata_path: str) -> pd.DataFrame:
    """
    Carga el fichero de metadata UniProt (TSV).

    Contiene: Entry, Entry Name, Reviewed, Gene Names, Organism, etc.
    """
    if not Path(metadata_path).exists():
        raise FileNotFoundError(f"Metadata no encontrado: {metadata_path}")

    df = pd.read_csv(metadata_path, sep='\t', dtype=str)
    if "Entry" not in df.columns:
        raise ValueError("El TSV de metadata debe tener una columna 'Entry'.")

    df = df.fillna('')
    # Drop duplicates and set Entry as index
    df = df.drop_duplicates(subset=["Entry"]).set_index("Entry")
    return df


def build_uniprot_docs(
    mapping_df: pd.DataFrame,
    metadata_df: pd.DataFrame,
    project_id: str,
    verbose: bool = True
) -> List[Dict[str, Any]]:
    """
    Construye documentos UniProt para un proyecto específico.

    Args:
        mapping_df: DataFrame con mapping ensembl/hgnc/uniprot
        metadata_df: DataFrame con metadata de UniProt (indexado por Entry)
        project_id: ID del proyecto (ej. 'TCGA-LGG')
        verbose: Si True, muestra información detallada

    Returns:
        Lista de documentos UniProt para este proyecto
    """
    if verbose:
        print(f"\nConstruyendo documentos UniProt para {project_id}...")

    # Add project_id column to mapping
    mapping_df = mapping_df.copy()
    mapping_df["project_id"] = project_id

    docs = []

    # Agrupar por uniprot_id (unidad básica de documento)
    for uniprot_id, group in mapping_df.groupby("uniprot_id"):
        all_hgnc_ids = sorted({v for v in group["hgnc_id"].dropna().unique() if v})
        all_ensembl_ids = sorted({v for v in group["ensembl_gene_id"].dropna().unique() if v})
        symbols = sorted({v for v in group["symbol"].dropna().unique() if v})

        # Bloque projects.<PROJECT>
        projects = {}
        for proj, proj_group in group.groupby("project_id"):
            proj_hgnc = sorted({v for v in proj_group["hgnc_id"].dropna().unique() if v})
            proj_ens = sorted({v for v in proj_group["ensembl_gene_id"].dropna().unique() if v})
            projects[proj] = {
                "present_in_mapping": True,
                "hgnc_ids": proj_hgnc,
                "ensembl_gene_ids": proj_ens,
            }

        # Metadata para este uniprot_id (puede no existir)
        meta = metadata_df.loc[uniprot_id] if uniprot_id in metadata_df.index else None

        if meta is not None:
            entry_name = _none_if_nan(meta.get("Entry Name"))
            reviewed = _bool_from_reviewed(meta.get("Reviewed"))
            gene_primary = _none_if_nan(meta.get("Gene Names (primary)"))
            gene_synonyms = _split_field(meta.get("Gene Names"), sep=" ")
            org_tax_id = _none_if_nan(meta.get("Organism (ID)"))
            protein_names = _none_if_nan(meta.get("Protein names"))
            length = _none_if_nan(meta.get("Length"))
            protein_existence = _none_if_nan(meta.get("Protein existence"))
            go_mf = _split_field(meta.get("Gene Ontology (molecular function)"), sep=";")
            go_bp = _split_field(meta.get("Gene Ontology (biological process)"), sep=";")
            go_cc = _split_field(meta.get("Gene Ontology (cellular component)"), sep=";")
            raw_cc_function = meta.get("Function [CC]")
            cc_function = _none_if_nan(raw_cc_function)
            cc_subcellular = _split_field(meta.get("Subcellular location [CC]"), sep=";")
        else:
            # Fallback mínimo si el mapping tiene entradas sin metadata
            entry_name = None
            reviewed = False
            gene_primary = symbols[0] if symbols else None
            gene_synonyms = symbols[1:] if len(symbols) > 1 else []
            org_tax_id = None
            protein_names = None
            length = None
            protein_existence = None
            go_mf = []
            go_bp = []
            go_cc = []
            cc_function = None
            cc_subcellular = []

        doc = {
            "_id": uniprot_id,
            "uniprot_id": uniprot_id,
            "entry_name": entry_name,
            "reviewed": reviewed,
            "organism": {
                "taxonomy_id": int(org_tax_id) if org_tax_id and str(org_tax_id).isdigit() else org_tax_id,
                "name": "Homo sapiens" if org_tax_id == "9606" else None,
            },
            "gene": {
                "primary_symbol": gene_primary or (symbols[0] if symbols else None),
                "synonyms": gene_synonyms or symbols,
                "hgnc_ids": all_hgnc_ids,
                "ensembl_gene_ids": all_ensembl_ids,
            },
            "protein": {
                "names": (
                    [protein_names]
                    if protein_names and ";" not in str(protein_names)
                    else _split_field(protein_names, sep=";")
                ),
                "length": int(length) if length and str(length).isdigit() else length,
                "existence_evidence": protein_existence,
                "function_cc": cc_function,
                "subcellular_location_cc": cc_subcellular,
            },
            "go_terms": {
                "molecular_function": go_mf,
                "biological_process": go_bp,
                "cellular_component": go_cc,
            },
            "projects": projects,
        }

        docs.append(doc)

    if verbose:
        print(f"  ✓ Construidos {len(docs)} documentos UniProt para {project_id}")

    return docs


def merge_uniprot_entries(all_project_docs: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """
    Merge UniProt entries from multiple projects into a unified list.

    Each UniProt entry (identified by uniprot_id) should have a "projects" field
    containing data from all projects it appears in.

    Args:
        all_project_docs: List of lists, where each inner list contains UniProt
                         documents for a single project

    Returns:
        List of merged UniProt entries with unified project information
    """
    # Dictionary to accumulate entries by uniprot_id
    merged_entries: Dict[str, Dict[str, Any]] = {}

    for project_docs in all_project_docs:
        for doc in project_docs:
            uniprot_id = doc["_id"]

            if uniprot_id not in merged_entries:
                # First time seeing this entry - add it
                merged_entries[uniprot_id] = doc
            else:
                # Already have this entry - merge the projects field
                existing_entry = merged_entries[uniprot_id]
                new_projects = doc.get("projects", {})

                # Merge projects dictionaries
                existing_entry["projects"].update(new_projects)

    return list(merged_entries.values())


def prepare_uniprot_entries_for_export(all_uniprot_entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Prepara las entradas UniProt para exportación como documentos individuales.

    Cada entrada UniProt se exporta como documento independiente con su uniprot_id como _id.
    Esto facilita consultas con find() e índices en MongoDB sin necesidad de $unwind.

    Estructura resultante (array de documentos):
    [
        {
            '_id': 'P12345',
            'uniprot_id': 'P12345',
            'entry_name': 'GENE_HUMAN',
            'reviewed': true,
            'gene': {...},
            'go_terms': {...},
            'projects': {
                'TCGA-LGG': {...},
                'TCGA-GBM': {...}
            }
        },
        ...
    ]

    Args:
        all_uniprot_entries: Lista de todas las entradas UniProt con información
                            de proyectos combinada

    Returns:
        Lista de documentos UniProt listos para MongoDB/JSON
    """
    # Los documentos ya vienen con _id = uniprot_id desde build_uniprot_docs
    return all_uniprot_entries


def convert_objectid_to_str(obj: Any) -> Any:
    """
    Convierte ObjectId de BSON a string para serialización JSON.

    Args:
        obj: Objeto que puede contener ObjectIds

    Returns:
        Objeto con ObjectIds convertidos a strings
    """
    if isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, dict):
        return {k: convert_objectid_to_str(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_objectid_to_str(item) for item in obj]
    else:
        return obj


def export_collection_to_json(
    mongo_uri: str,
    database_name: str,
    collection_name: str,
    output_path: str,
    verbose: bool = True
) -> bool:
    """
    Exporta la colección MongoDB a un archivo JSON.

    Args:
        mongo_uri: URI de conexión a MongoDB
        database_name: Nombre de la base de datos
        collection_name: Nombre de la colección
        output_path: Ruta donde guardar el archivo JSON
        verbose: Si True, muestra información detallada

    Returns:
        True si la exportación fue exitosa, False en caso contrario
    """
    try:
        # Conectar a MongoDB usando context manager para asegurar el cierre
        with MongoClient(mongo_uri) as client:
            db = client[database_name]
            collection = db[collection_name]

            if verbose:
                print(f"\n[Exportación JSON] Recuperando documentos de MongoDB...")

            # Obtener todos los documentos de la colección
            documents = list(collection.find())

            if not documents:
                if verbose:
                    print(f"[Exportación JSON] Advertencia: La colección '{collection_name}' está vacía")
                return False

            if verbose:
                print(f"[Exportación JSON] Recuperados {len(documents)} documento(s)")

            # Convertir ObjectIds a strings para serialización JSON
            documents_serializable = convert_objectid_to_str(documents)

            # Crear directorio si no existe
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Guardar como JSON
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(documents_serializable, f, indent=2, ensure_ascii=False)

            if verbose:
                file_size = output_file.stat().st_size
                file_size_mb = file_size / (1024 * 1024)
                print(f"[Exportación JSON] Colección exportada exitosamente")
                print(f"  - Archivo: {output_path}")
                print(f"  - Tamaño: {file_size_mb:.2f} MB ({file_size:,} bytes)")
                print(f"  - Documentos: {len(documents)}")

            return True

    except Exception as e:
        if verbose:
            print(f"[Exportación JSON] Error durante la exportación: {e}")
        return False


def save_documents_as_json(
    documents: List[Dict[str, Any]],
    output_path: str,
    verbose: bool = True
) -> bool:
    """
    Guarda una lista de documentos como archivo JSON (sin insertar en MongoDB).

    Args:
        documents: Lista de documentos a guardar (array de entradas UniProt)
        output_path: Ruta donde guardar el archivo JSON
        verbose: Si True, muestra información detallada

    Returns:
        True si el guardado fue exitoso, False en caso contrario
    """
    try:
        if verbose:
            print(f"\n[Guardado JSON] Guardando {len(documents)} documento(s) como JSON...")

        # Crear directorio si no existe
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Guardar como JSON (array de documentos)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(documents, f, indent=2, ensure_ascii=False)

        if verbose:
            file_size = output_file.stat().st_size
            file_size_mb = file_size / (1024 * 1024)
            print(f"[Guardado JSON] Documentos guardados exitosamente")
            print(f"  - Archivo: {output_path}")
            print(f"  - Tamaño: {file_size_mb:.2f} MB ({file_size:,} bytes)")
            print(f"  - Documentos: {len(documents)}")

        return True

    except Exception as e:
        if verbose:
            print(f"[Guardado JSON] Error durante el guardado: {e}")
        return False


def insert_to_mongo(
    document: Dict[str, Any],
    mongo_uri: str,
    database_name: str,
    collection_name: str,
    drop_collection: bool = False,
    save_as_json_uniprot: Optional[str] = None,
    verbose: bool = True
) -> None:
    """
    Inserta el documento en MongoDB.

    Args:
        document: Documento a insertar
        mongo_uri: URI de conexión a MongoDB
        database_name: Nombre de la base de datos
        collection_name: Nombre de la colección
        drop_collection: Si True, elimina la colección antes de insertar
        save_as_json_uniprot: Ruta donde guardar la colección como JSON (None = no guardar)
        verbose: Si True, muestra información detallada
    """
    try:
        # Conectar a MongoDB
        client = MongoClient(mongo_uri)
        db = client[database_name]
        collection = db[collection_name]

        if verbose:
            print(f"\nConectado a MongoDB:")
            print(f"  - Base de datos: {database_name}")
            print(f"  - Colección: {collection_name}")

        # Eliminar colección si se solicita
        if drop_collection:
            collection.drop()
            if verbose:
                print(f"  - Colección '{collection_name}' eliminada")

        # Insertar/actualizar documento
        result = collection.update_one(
            {'_id': document['_id']},
            {'$set': document},
            upsert=True
        )

        if verbose:
            print(f"\n--- Resultados de la Importación ---")
            if result.upserted_id:
                print(f"Documento insertado: {result.upserted_id}")
            else:
                print(f"Documento actualizado: {document['_id']}")
            print("¡Importación de UniProt completada con éxito!")

        client.close()

        # Exportar a JSON si se especificó
        if save_as_json_uniprot:
            export_collection_to_json(
                mongo_uri=mongo_uri,
                database_name=database_name,
                collection_name=collection_name,
                output_path=save_as_json_uniprot,
                verbose=verbose
            )

    except Exception as e:
        print(f"Error durante la inserción en MongoDB: {e}")
        sys.exit(1)


def run_import(
    uniprot_config: 'UniProtMongoDataConfig',
    mongo_uri: str,
    database_name: str,
    collection_name: str,
    insert_into_mongodb: bool = True,
    drop_collection: bool = False,
    save_as_json_uniprot: Optional[str] = None,
    verbose: bool = True
) -> None:
    """
    Función principal que orquesta todo el proceso de importación multi-proyecto UniProt.

    Multi-project support: Procesa todos los proyectos configurados y los combina
    en un único documento MongoDB con uniprot_entries array.

    Args:
        uniprot_config: Configuración UniProt con lista de proyectos
        mongo_uri: URI de MongoDB
        database_name: Nombre de la base de datos
        collection_name: Nombre de la colección
        insert_into_mongodb: Si True, inserta en MongoDB; si False, solo genera JSON
        drop_collection: Si True, elimina la colección antes de insertar
        save_as_json_uniprot: Ruta donde guardar el documento como JSON
        verbose: Si True, muestra información detallada
    """
    if verbose:
        print("=" * 100)
        print("IMPORTADOR UNIPROT MULTI-PROYECTO A MONGODB")
        print("=" * 100)
        print(f"\nProcesando {len(uniprot_config.projects)} proyecto(s):")
        for proj in uniprot_config.projects:
            print(f"  - {proj.project_id}")
        print("=" * 100)

    all_project_docs = []

    # Process each project
    for project_idx, project_meta in enumerate(uniprot_config.projects, 1):
        if verbose:
            print(f"\n{'=' * 100}")
            print(f"PROCESANDO PROYECTO {project_idx}/{len(uniprot_config.projects)}: {project_meta.project_id}")
            print(f"{'=' * 100}")

        try:
            # Build project-specific file paths
            base_dir = Path(uniprot_config.base_data_dir).expanduser().resolve()
            project_dir = base_dir / project_meta.project_id

            # Replace {project_id_lower} in filename patterns
            project_id_lower = project_meta.project_id.lower().replace("-", "_")
            mapping_filename = uniprot_config.mapping_filename.replace("{project_id_lower}", project_id_lower)
            metadata_filename = uniprot_config.metadata_filename.replace("{project_id_lower}", project_id_lower)

            mapping_path = project_dir / mapping_filename
            metadata_path = project_dir / metadata_filename

            if verbose:
                print(f"\n[1/2] Cargando ficheros TSV para {project_meta.project_id}...")
                print(f"  - Mapping: {mapping_path}")
                print(f"  - Metadata: {metadata_path}")

            # Verify files exist
            if not mapping_path.exists():
                raise FileNotFoundError(f"Mapping no encontrado: {mapping_path}")
            if not metadata_path.exists():
                raise FileNotFoundError(f"Metadata no encontrado: {metadata_path}")

            # Load TSV files
            mapping_df = load_uniprot_mapping(str(mapping_path))
            if verbose:
                print(f"  ✓ Mapping cargado: {len(mapping_df)} filas")

            metadata_df = load_uniprot_metadata(str(metadata_path))
            if verbose:
                print(f"  ✓ Metadata cargado: {len(metadata_df)} entradas UniProt")

            # Build project documents
            if verbose:
                print(f"\n[2/2] Construyendo documentos UniProt para {project_meta.project_id}...")

            project_docs = build_uniprot_docs(
                mapping_df=mapping_df,
                metadata_df=metadata_df,
                project_id=project_meta.project_id,
                verbose=verbose
            )

            all_project_docs.append(project_docs)

        except Exception as e:
            print(f"\n✗ ERROR procesando proyecto {project_meta.project_id}: {e}")
            raise

    # Merge UniProt entries from all projects
    if verbose:
        print(f"\n{'=' * 100}")
        print(f"COMBINANDO ENTRADAS UNIPROT DE TODOS LOS PROYECTOS...")
        print(f"{'=' * 100}")

    merged_entries = merge_uniprot_entries(all_project_docs)

    if verbose:
        print(f"\n  ✓ Entradas UniProt combinadas: {len(merged_entries)}")

    # Preparar documentos para exportación (array de entradas individuales)
    if verbose:
        print(f"\n{'=' * 100}")
        print(f"PREPARANDO ENTRADAS UNIPROT PARA EXPORTACIÓN...")
        print(f"{'=' * 100}")

    export_documents = prepare_uniprot_entries_for_export(merged_entries)

    if verbose:
        print(f"\n  ✓ Documentos preparados (array de entradas individuales):")
        print(f"    - Total entradas UniProt: {len(export_documents)}")

    # Handle insert_into_mongodb flag
    if not insert_into_mongodb:
        if verbose:
            print(f"\n{'=' * 100}")
            print("MODO SOLO JSON: No insertando en MongoDB...")
            print(f"{'=' * 100}")

        if not save_as_json_uniprot:
            # Generate default output path
            save_as_json_uniprot = "uniprot_entries_export.json"

        save_documents_as_json(
            documents=export_documents,
            output_path=save_as_json_uniprot,
            verbose=verbose
        )

        if verbose:
            print(f"\n{'=' * 100}")
            print("✓ PROCESO COMPLETADO EXITOSAMENTE (sin inserción en MongoDB)")
            print(f"{'=' * 100}")
    else:
        # Insert to MongoDB - insertar cada entrada como documento individual
        if verbose:
            print(f"\n{'=' * 100}")
            print("INSERTANDO EN MONGODB...")
            print(f"{'=' * 100}")

        # Insertar cada entrada UniProt como documento independiente
        first_doc = True
        for uniprot_doc in export_documents:
            insert_to_mongo(
                document=uniprot_doc,
                mongo_uri=mongo_uri,
                database_name=database_name,
                collection_name=collection_name,
                drop_collection=drop_collection if first_doc else False,
                save_as_json_uniprot=None,  # No exportar JSON aquí, lo haremos al final
                verbose=False  # Reducir verbosidad para muchos documentos
            )
            first_doc = False

        if verbose:
            print(f"  ✓ Insertados {len(export_documents)} documentos UniProt")

        # Exportar colección completa a JSON si se especificó
        if save_as_json_uniprot:
            export_collection_to_json(
                mongo_uri=mongo_uri,
                database_name=database_name,
                collection_name=collection_name,
                output_path=save_as_json_uniprot,
                verbose=verbose
            )

        if verbose:
            print(f"\n{'=' * 100}")
            print("✓ PROCESO COMPLETADO EXITOSAMENTE")
            print(f"{'=' * 100}")
