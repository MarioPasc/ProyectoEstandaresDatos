"""
import_hgnc_mongo.py

Importador de datos HGNC combinados con datos de expresión de GDC a MongoDB.
Construye una colección con estructura jerárquica:
  Gene (HGNC) → Projects → Cases (con datos de expresión)

Issue: #16 - HGNC + GDC Expression Integration
"""

import os
import sys
import json
import math
from pathlib import Path
from typing import Dict, Optional, Any, List

import pandas as pd
from pymongo import MongoClient
from bson import ObjectId


def _none_if_nan(value):
    """Convierte valores NaN a None para compatibilidad con JSON/MongoDB."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _split_field(value, sep="|"):
    """Divide campos de texto (HGNC usa pipes '|'). Retorna lista limpia."""
    value = _none_if_nan(value)
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    return [p.strip() for p in text.split(sep) if p.strip()]


def load_hgnc_data(hgnc_tsv_path: str, verbose: bool = True) -> pd.DataFrame:
    """
    Carga el fichero HGNC complete set TSV.

    Args:
        hgnc_tsv_path: Ruta al fichero HGNC TSV
        verbose: Si True, muestra información detallada

    Returns:
        DataFrame con los datos HGNC filtrados (solo filas con hgnc_id y ensembl_gene_id)
    """
    if not os.path.exists(hgnc_tsv_path):
        raise FileNotFoundError(f"Fichero HGNC no encontrado: {hgnc_tsv_path}")

    if verbose:
        print(f"Cargando datos HGNC desde {os.path.basename(hgnc_tsv_path)}...")

    df = pd.read_csv(hgnc_tsv_path, sep='\t', dtype=str)

    # Filtrar filas inválidas (sin IDs)
    df = df.dropna(subset=['hgnc_id', 'ensembl_gene_id'])

    if verbose:
        print(f"  ✓ {len(df)} genes HGNC cargados")

    return df


def get_downloaded_star_counts_files(
    star_counts_dir: Path,
    verbose: bool = True
) -> List[Path]:
    """
    Escanea el directorio star_counts y retorna una lista de ficheros .tsv descargados.

    Args:
        star_counts_dir: Directorio donde están los ficheros STAR-counts
        verbose: Si True, muestra información detallada

    Returns:
        Lista de rutas a ficheros .tsv encontrados
    """
    if not star_counts_dir.exists():
        if verbose:
            print(f"  [WARN] Directorio star_counts no encontrado: {star_counts_dir}")
        return []

    # Búsqueda de ficheros .tsv
    files = list(star_counts_dir.glob("*.tsv"))

    if not files:
        # Búsqueda recursiva si no se encuentran en el nivel superior
        files = list(star_counts_dir.glob("**/*.tsv"))

    if verbose:
        print(f"  ✓ {len(files)} ficheros STAR-counts encontrados en {star_counts_dir.name}")

    return files


def load_file_metadata(metadata_path: Path, verbose: bool = True) -> pd.DataFrame:
    """
    Carga el fichero de metadatos fichero-caso (TSV).

    Args:
        metadata_path: Ruta al fichero de metadata
        verbose: Si True, muestra información detallada

    Returns:
        DataFrame con metadatos (file_id, case_id, submitter_id, etc.)
    """
    if not metadata_path.exists():
        raise FileNotFoundError(f"Metadata no encontrado: {metadata_path}")

    df = pd.read_csv(metadata_path, sep='\t', dtype=str, low_memory=False)
    df = df.fillna('')

    # Normalizar columnas a minúsculas
    df.columns = [c.lower() for c in df.columns]

    if verbose:
        print(f"  ✓ Metadata cargado: {len(df)} relaciones caso-fichero")

    return df


def load_expression_data_from_file(
    file_path: Path,
    strip_version: bool = True,
    verbose: bool = False
) -> Dict[str, Dict[str, float]]:
    """
    Procesa un fichero STAR-Counts y extrae los datos de expresión por gen.

    Args:
        file_path: Ruta al fichero STAR-counts
        strip_version: Si True, elimina versiones de Ensembl IDs (ej. ENSG00000121410.8 -> ENSG00000121410)
        verbose: Si True, muestra información detallada

    Returns:
        Diccionario {ensembl_gene_id: {unstranded: X, stranded_first: Y, ...}}
    """
    expression_data = {}

    try:
        df = pd.read_csv(file_path, sep='\t', comment='#', low_memory=False)

        # Expected columns: gene_id, gene_name, gene_type, unstranded, stranded_first, stranded_second, tpm_unstranded, fpkm_unstranded, fpkm_uq_unstranded
        # Normalizar nombres de columnas
        df.columns = [c.lower() for c in df.columns]

        if 'gene_id' not in df.columns:
            if verbose:
                print(f"  [WARN] Columna 'gene_id' no encontrada en {file_path.name}")
            return expression_data

        for _, row in df.iterrows():
            gene_id = row.get('gene_id', '').strip()

            # Ignorar métricas de STAR (N_unmapped, etc.)
            if not gene_id or gene_id.startswith('N_'):
                continue

            # Eliminar versión si se solicita
            if strip_version and '.' in gene_id:
                gene_id = gene_id.split('.')[0]

            # Extraer valores de expresión
            expression_values = {}

            # Intentar extraer todas las columnas de expresión disponibles
            expr_columns = [
                'unstranded', 'stranded_first', 'stranded_second',
                'tpm_unstranded', 'fpkm_unstranded', 'fpkm_uq_unstranded'
            ]

            for col in expr_columns:
                if col in df.columns:
                    value = row.get(col)
                    # Convertir a float si es posible, None si es NaN
                    if pd.notna(value):
                        try:
                            expression_values[col] = float(value)
                        except (ValueError, TypeError):
                            expression_values[col] = None
                    else:
                        expression_values[col] = None

            expression_data[gene_id] = expression_values

    except Exception as e:
        if verbose:
            print(f"  [ERROR] Error procesando {file_path.name}: {e}")

    return expression_data


def get_case_id_from_filename(
    file_name: str,
    metadata_df: pd.DataFrame,
    verbose: bool = False
) -> Optional[str]:
    """
    Busca el case_id correspondiente a un file_name en el metadata.

    Args:
        file_name: Nombre del fichero (ej. "abc123.rna_seq.augmented_star_gene_counts.tsv")
        metadata_df: DataFrame con metadatos
        verbose: Si True, muestra información detallada

    Returns:
        case_id si se encuentra, None en caso contrario
    """
    # Buscar por nombre exacto
    match = metadata_df[metadata_df['file_name'] == file_name]

    if match.empty:
        if verbose:
            print(f"  [WARN] No se encontró case_id para fichero: {file_name}")
        return None

    # Buscar columna case_id
    col_case = next((c for c in metadata_df.columns if 'case_id' in c and 'project' not in c), None)

    if not col_case:
        if verbose:
            print(f"  [WARN] Columna case_id no encontrada en metadata")
        return None

    case_id = match.iloc[0][col_case]
    return case_id if case_id else None


def get_file_id_from_filename(
    file_name: str,
    metadata_df: pd.DataFrame,
    verbose: bool = False
) -> Optional[str]:
    """
    Busca el file_id correspondiente a un file_name en el metadata.

    Args:
        file_name: Nombre del fichero
        metadata_df: DataFrame con metadatos
        verbose: Si True, muestra información detallada

    Returns:
        file_id si se encuentra, None en caso contrario
    """
    match = metadata_df[metadata_df['file_name'] == file_name]

    if match.empty:
        return None

    col_file = next((c for c in metadata_df.columns if 'file_id' in c), None)

    if not col_file:
        return None

    file_id = match.iloc[0][col_file]
    return file_id if file_id else None


def build_hgnc_documents(
    hgnc_df: pd.DataFrame,
    gdc_config: 'GDCMongoDataConfig',
    verbose: bool = True
) -> List[Dict[str, Any]]:
    """
    Construye documentos HGNC con datos de expresión de todos los proyectos GDC.

    Estructura del documento:
    {
        "_id": "HGNC:12345",
        "hgnc_id": "HGNC:12345",
        "symbol": "TP53",
        "ensembl_gene_id": "ENSG00000141510",
        "uniprot_ids": ["P04637"],
        "projects": {
            "TCGA-GBM": {
                "n_cases": 5,
                "cases": {
                    "case-abc123": {
                        "file_id": "file-xyz789",
                        "unstranded": 1234,
                        "stranded_first": 567,
                        ...
                    }
                }
            }
        }
    }

    Args:
        hgnc_df: DataFrame con datos HGNC
        gdc_config: Configuración GDC con lista de proyectos
        verbose: Si True, muestra información detallada

    Returns:
        Lista de documentos HGNC con datos de expresión
    """
    if verbose:
        print(f"\n{'=' * 100}")
        print("CONSTRUYENDO DOCUMENTOS HGNC CON DATOS DE EXPRESIÓN GDC")
        print(f"{'=' * 100}")

    # Inicializar documentos base para todos los genes HGNC
    gene_documents = {}

    for _, row in hgnc_df.iterrows():
        ens_id = row['ensembl_gene_id'].strip()
        hgnc_id = row['hgnc_id'].strip()

        gene_documents[ens_id] = {
            "_id": hgnc_id,
            "hgnc_id": hgnc_id,
            "symbol": row['symbol'],
            "ensembl_gene_id": ens_id,
            "uniprot_ids": _split_field(row.get('uniprot_ids', ''), sep="|"),
            "projects": {}
        }

    if verbose:
        print(f"  ✓ {len(gene_documents)} genes HGNC inicializados")

    # Procesar cada proyecto
    for project_idx, project_meta in enumerate(gdc_config.projects, 1):
        if verbose:
            print(f"\n{'=' * 60}")
            print(f"Procesando proyecto {project_idx}/{len(gdc_config.projects)}: {project_meta.project_id}")
            print(f"{'=' * 60}")

        try:
            base_dir = Path(gdc_config.base_data_dir).expanduser().resolve()
            project_dir = base_dir / project_meta.project_id

            # Construir rutas de ficheros
            project_id_lower = project_meta.project_id.lower().replace("-", "_")
            metadata_filename = gdc_config.metadata_filename.replace("{project_id_lower}", project_id_lower)
            metadata_path = project_dir / metadata_filename
            star_counts_dir = project_dir / gdc_config.star_counts_dirname

            if verbose:
                print(f"\n[1/3] Cargando metadata para {project_meta.project_id}...")

            # Cargar metadata
            metadata_df = load_file_metadata(metadata_path, verbose=verbose)

            if verbose:
                print(f"\n[2/3] Escaneando ficheros STAR-counts descargados...")

            # Obtener ficheros descargados
            downloaded_files = get_downloaded_star_counts_files(star_counts_dir, verbose=verbose)

            if not downloaded_files:
                if verbose:
                    print(f"  [WARN] No se encontraron ficheros descargados para {project_meta.project_id}")
                continue

            if verbose:
                print(f"\n[3/3] Procesando datos de expresión...")

            # Procesar cada fichero descargado
            cases_processed = 0
            genes_with_expression = set()

            for file_path in downloaded_files:
                file_name = file_path.name

                # Obtener case_id y file_id del metadata
                case_id = get_case_id_from_filename(file_name, metadata_df, verbose=False)
                file_id = get_file_id_from_filename(file_name, metadata_df, verbose=False)

                if not case_id:
                    if verbose:
                        print(f"  [SKIP] No se pudo obtener case_id para {file_name}")
                    continue

                # Cargar datos de expresión del fichero
                expression_data = load_expression_data_from_file(file_path, strip_version=True, verbose=False)

                if not expression_data:
                    if verbose:
                        print(f"  [SKIP] No se pudieron extraer datos de expresión de {file_name}")
                    continue

                # Agregar datos de expresión a los genes correspondientes
                for ensembl_id, expr_values in expression_data.items():
                    if ensembl_id in gene_documents:
                        # Inicializar estructura del proyecto si no existe
                        if project_meta.project_id not in gene_documents[ensembl_id]["projects"]:
                            gene_documents[ensembl_id]["projects"][project_meta.project_id] = {
                                "n_cases": 0,
                                "cases": {}
                            }

                        # Agregar caso con datos de expresión
                        gene_documents[ensembl_id]["projects"][project_meta.project_id]["cases"][case_id] = {
                            "file_id": file_id,
                            **expr_values
                        }

                        genes_with_expression.add(ensembl_id)

                cases_processed += 1

            # Actualizar n_cases para cada gen en este proyecto
            for ensembl_id in genes_with_expression:
                if project_meta.project_id in gene_documents[ensembl_id]["projects"]:
                    gene_documents[ensembl_id]["projects"][project_meta.project_id]["n_cases"] = \
                        len(gene_documents[ensembl_id]["projects"][project_meta.project_id]["cases"])

            if verbose:
                print(f"\n  ✓ Proyecto {project_meta.project_id} procesado:")
                print(f"    - Casos procesados: {cases_processed}")
                print(f"    - Genes con expresión: {len(genes_with_expression)}")

        except Exception as e:
            print(f"\n  ✗ ERROR procesando proyecto {project_meta.project_id}: {e}")
            import traceback
            traceback.print_exc()
            continue

    # Convertir a lista de documentos
    documents = list(gene_documents.values())

    if verbose:
        # Estadísticas finales
        genes_with_projects = sum(1 for doc in documents if doc["projects"])
        total_projects_count = sum(len(doc["projects"]) for doc in documents)

        print(f"\n{'=' * 100}")
        print(f"RESUMEN DE CONSTRUCCIÓN DE DOCUMENTOS:")
        print(f"  - Total genes HGNC: {len(documents)}")
        print(f"  - Genes con datos de expresión: {genes_with_projects}")
        print(f"  - Total asociaciones gen-proyecto: {total_projects_count}")
        print(f"{'=' * 100}")

    return documents


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
        with MongoClient(mongo_uri) as client:
            db = client[database_name]
            collection = db[collection_name]

            if verbose:
                print(f"\n[Exportación JSON] Recuperando documentos de MongoDB...")

            documents = list(collection.find())

            if not documents:
                if verbose:
                    print(f"[Exportación JSON] Advertencia: La colección '{collection_name}' está vacía")
                return False

            if verbose:
                print(f"[Exportación JSON] Recuperados {len(documents)} documento(s)")

            # Convertir ObjectIds a strings
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


def insert_to_mongo(
    documents: List[Dict[str, Any]],
    mongo_uri: str,
    database_name: str,
    collection_name: str,
    drop_collection: bool = False,
    save_as_json: Optional[str] = None,
    verbose: bool = True
) -> None:
    """
    Inserta los documentos HGNC en MongoDB.

    Args:
        documents: Lista de documentos a insertar
        mongo_uri: URI de conexión a MongoDB
        database_name: Nombre de la base de datos
        collection_name: Nombre de la colección
        drop_collection: Si True, elimina la colección antes de insertar
        save_as_json: Ruta donde guardar la colección como JSON (None = no guardar)
        verbose: Si True, muestra información detallada
    """
    try:
        client = MongoClient(mongo_uri)
        db = client[database_name]
        collection = db[collection_name]

        if verbose:
            print(f"\n{'=' * 100}")
            print(f"INSERTANDO EN MONGODB")
            print(f"{'=' * 100}")
            print(f"  - Base de datos: {database_name}")
            print(f"  - Colección: {collection_name}")
            print(f"  - Documentos a insertar: {len(documents)}")

        # Eliminar colección si se solicita
        if drop_collection:
            collection.drop()
            if verbose:
                print(f"  ✓ Colección '{collection_name}' eliminada")

        # Insertar documentos (bulk upsert)
        if verbose:
            print(f"\nInsertando documentos...")

        inserted_count = 0
        updated_count = 0

        for doc in documents:
            result = collection.update_one(
                {'_id': doc['_id']},
                {'$set': doc},
                upsert=True
            )

            if result.upserted_id:
                inserted_count += 1
            else:
                updated_count += 1

        if verbose:
            print(f"\n{'=' * 100}")
            print(f"RESULTADOS DE LA IMPORTACIÓN")
            print(f"{'=' * 100}")
            print(f"  - Documentos insertados: {inserted_count}")
            print(f"  - Documentos actualizados: {updated_count}")
            print(f"  ✓ Importación de HGNC completada con éxito!")

        client.close()

        # Exportar a JSON si se especificó
        if save_as_json:
            export_collection_to_json(
                mongo_uri=mongo_uri,
                database_name=database_name,
                collection_name=collection_name,
                output_path=save_as_json,
                verbose=verbose
            )

    except Exception as e:
        print(f"Error durante la inserción en MongoDB: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def run_import(
    hgnc_config: 'HGNCMongoConfig',
    gdc_config: 'GDCMongoDataConfig',
    mongo_uri: str,
    database_name: str,
    insert_into_mongodb: bool = True,
    drop_collection: bool = False,
    save_as_json_hgnc: Optional[str] = None,
    verbose: bool = True
) -> None:
    """
    Función principal que orquesta todo el proceso de importación HGNC.

    Args:
        hgnc_config: Configuración HGNC
        gdc_config: Configuración GDC con lista de proyectos
        mongo_uri: URI de MongoDB
        database_name: Nombre de la base de datos
        insert_into_mongodb: Si True, inserta en MongoDB; si False, solo genera JSON
        drop_collection: Si True, elimina la colección antes de insertar
        save_as_json_hgnc: Ruta donde guardar el documento como JSON
        verbose: Si True, muestra información detallada
    """
    if verbose:
        print(f"{'=' * 100}")
        print("IMPORTADOR HGNC + GDC EXPRESSION A MONGODB")
        print(f"{'=' * 100}")
        print(f"\nProcesando:")
        print(f"  - HGNC TSV: {hgnc_config.hgnc_tsv_path}")
        print(f"  - Proyectos GDC: {len(gdc_config.projects)}")
        for proj in gdc_config.projects:
            print(f"    • {proj.project_id}: {proj.disease_type}")
        print(f"{'=' * 100}")

    # Cargar datos HGNC
    hgnc_df = load_hgnc_data(hgnc_config.hgnc_tsv_path, verbose=verbose)

    # Construir documentos
    documents = build_hgnc_documents(hgnc_df, gdc_config, verbose=verbose)

    # Handle insert_into_mongodb flag
    if not insert_into_mongodb:
        if verbose:
            print(f"\n{'=' * 100}")
            print(f"MODO SOLO JSON: No insertando en MongoDB...")
            print(f"{'=' * 100}")

        if not save_as_json_hgnc:
            # Generate default output path
            save_as_json_hgnc = "hgnc_genes_export.json"

        # Crear directorio si no existe
        output_file = Path(save_as_json_hgnc)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Guardar como JSON
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(documents, f, indent=2, ensure_ascii=False)

        if verbose:
            file_size = output_file.stat().st_size
            file_size_mb = file_size / (1024 * 1024)
            print(f"\n  ✓ Colección exportada como JSON:")
            print(f"    - Archivo: {save_as_json_hgnc}")
            print(f"    - Tamaño: {file_size_mb:.2f} MB ({file_size:,} bytes)")
            print(f"    - Documentos: {len(documents)}")
    else:
        # Insertar en MongoDB + exportar JSON
        insert_to_mongo(
            documents=documents,
            mongo_uri=mongo_uri,
            database_name=database_name,
            collection_name=hgnc_config.collection_name,
            drop_collection=drop_collection,
            save_as_json=save_as_json_hgnc,
            verbose=verbose
        )

    if verbose:
        print(f"\n{'=' * 100}")
        print("✓ PROCESO COMPLETADO EXITOSAMENTE")
        print(f"{'=' * 100}")
