"""
import_gdc_mongo.py

Importador de datos GDC a MongoDB.
Construye una colección con estructura jerárquica:
  Proyecto → Casos → Ficheros (con expression_summary)

Issue: T1 - GDC MongoDB Import Task
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Optional, Any, List

import pandas as pd
import numpy as np
from pymongo import MongoClient
from bson import ObjectId


def load_manifest(manifest_path: str) -> pd.DataFrame:
    """
    Carga el fichero manifest de GDC (TSV).

    Contiene: file_id, file_name, md5sum, file_size, state
    """
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"Manifest no encontrado: {manifest_path}")

    df = pd.read_csv(manifest_path, sep='\t', low_memory=False)
    df = df.fillna('')
    return df


def load_file_metadata(metadata_path: str) -> pd.DataFrame:
    """
    Carga el fichero de metadatos fichero-caso-muestra (TSV).

    Contiene: cases.0.case_id, cases.0.submitter_id, file_id, file_name, etc.
    """
    if not os.path.exists(metadata_path):
        raise FileNotFoundError(f"Metadata no encontrado: {metadata_path}")

    df = pd.read_csv(metadata_path, sep='\t', low_memory=False)
    df = df.fillna('')
    return df


def load_genes_table(genes_path: str) -> pd.DataFrame:
    """
    Carga la tabla de genes del proyecto (TSV).

    Contiene: ensembl_gene_id_gdc, ensembl_gene_id
    """
    if not os.path.exists(genes_path):
        print(f"Advertencia: Tabla de genes no encontrada: {genes_path}")
        return pd.DataFrame()

    df = pd.read_csv(genes_path, sep='\t', low_memory=False)
    df = df.fillna('')
    return df


def process_star_counts_file(file_path: str) -> Dict[str, Any]:
    """
    Procesa un fichero STAR-Counts y calcula estadísticas de expresión.

    Returns:
        Dict con n_genes, mean, median, std de los valores de expresión
    """
    try:
        # Los ficheros STAR-Counts tienen formato:
        # gene_id  gene_name  gene_type  unstranded  stranded_first  stranded_second  ...
        df = pd.read_csv(file_path, sep='\t', comment='#', low_memory=False)

        # La columna de counts suele ser 'unstranded', 'stranded_first' o 'stranded_second'
        # Usamos 'unstranded' por defecto
        count_column = 'unstranded'

        if count_column not in df.columns:
            # Intentar encontrar una columna con valores numéricos
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) > 0:
                count_column = numeric_cols[0]
            else:
                return {
                    'n_genes': len(df),
                    'stats': {
                        'mean': None,
                        'median': None,
                        'std': None
                    }
                }

        # Calcular estadísticas
        counts = df[count_column].dropna()

        summary = {
            'n_genes': len(df),
            'stats': {
                'mean': float(counts.mean()) if len(counts) > 0 else None,
                'median': float(counts.median()) if len(counts) > 0 else None,
                'std': float(counts.std()) if len(counts) > 0 else None
            }
        }

        return summary

    except Exception as e:
        print(f"Advertencia: Error procesando {file_path}: {e}")
        return {
            'n_genes': None,
            'stats': {
                'mean': None,
                'median': None,
                'std': None
            }
        }


def build_gdc_document(
    manifest_df: pd.DataFrame,
    metadata_df: pd.DataFrame,
    project_id: str,
    disease_type: str,
    primary_site: str,
    data_category: str,
    star_counts_dir: Optional[str] = None,
    process_expression: bool = False,
    max_files: Optional[int] = None,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Construye el documento MongoDB con estructura jerárquica.

    Proyecto → Casos → Ficheros (con expression_summary opcional)

    Args:
        manifest_df: DataFrame con info de ficheros
        metadata_df: DataFrame con relación caso-fichero
        project_id: ID del proyecto (ej. 'TCGA-LGG')
        disease_type: Tipo de enfermedad
        primary_site: Sitio primario
        data_category: Categoría de datos
        star_counts_dir: Directorio con ficheros STAR-Counts
        process_expression: Si True, procesa ficheros STAR-Counts
        max_files: Máximo número de ficheros a procesar (None = todos)
        verbose: Si True, muestra información detallada

    Returns:
        Documento MongoDB con estructura completa
    """
    if verbose:
        print("\nConstruyendo documento MongoDB...")

    # Diccionario para agrupar ficheros por caso
    cases_dict: Dict[str, Dict[str, Any]] = {}

    # Contador de ficheros procesados
    files_processed = 0

    for _, row in metadata_df.iterrows():
        # Verificar límite de ficheros
        if max_files is not None and files_processed >= max_files:
            if verbose:
                print(f"Alcanzado límite de {max_files} ficheros. Deteniendo procesamiento.")
            break

        case_id = row.get('cases.0.case_id')
        submitter_id = row.get('cases.0.submitter_id')
        file_id = row.get('file_id')

        # Saltar si no hay case_id o file_id
        if not case_id or not file_id:
            continue

        # Crear entrada para el caso si no existe
        if case_id not in cases_dict:
            cases_dict[case_id] = {
                'case_id': case_id,
                'submitter_id': submitter_id,
                'files': []
            }

        # Buscar información del fichero en manifest
        file_info = manifest_df[manifest_df['file_id'] == file_id]

        if file_info.empty:
            if verbose:
                print(f"Advertencia: fichero {file_id} no encontrado en manifest")
            continue

        file_data = file_info.iloc[0]

        # Construir información del fichero
        file_size_value = file_data.get('file_size', '')
        file_doc = {
            'file_id': str(file_data.get('file_id', '')),
            'file_name': str(file_data.get('file_name', '')),
            'file_size': int(file_size_value) if file_size_value not in (None, '') else None,
            'md5sum': str(file_data.get('md5sum', '')),
            'state': str(file_data.get('state', ''))
        }

        # Procesar expresión si está habilitado
        if process_expression and star_counts_dir:
            file_name = file_doc['file_name']

            # Los ficheros pueden estar comprimidos (.gz) o descomprimidos
            star_file_path = Path(star_counts_dir) / file_name
            star_file_gz = Path(star_counts_dir) / f"{file_name}.gz"

            if star_file_path.exists():
                if verbose:
                    print(f"Procesando expresión para {file_name}...")
                file_doc['expression_summary'] = process_star_counts_file(str(star_file_path))
            elif star_file_gz.exists():
                # Si está comprimido, podríamos descomprimirlo temporalmente
                # Por ahora, solo marcamos que no está disponible
                if verbose:
                    print(f"Fichero {file_name} está comprimido (.gz), saltando procesamiento de expresión")
                file_doc['expression_summary'] = None
            else:
                if verbose:
                    print(f"Fichero STAR-Counts no encontrado: {file_name}")
                file_doc['expression_summary'] = None
        else:
            # No procesar expresión
            file_doc['expression_summary'] = None

        # Añadir fichero al caso
        cases_dict[case_id]['files'].append(file_doc)
        files_processed += 1

    # Construir documento final del proyecto
    document = {
        '_id': project_id,
        'project_id': project_id,
        'disease_type': disease_type,
        'primary_site': primary_site,
        'data_category': data_category,
        'cases': list(cases_dict.values())
    }

    if verbose:
        print(f"\nDocumento construido:")
        print(f"  - Proyecto: {project_id}")
        print(f"  - Casos: {len(cases_dict)}")
        print(f"  - Ficheros procesados: {files_processed}")

    return document


def build_multi_project_document(project_documents: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Construye un documento MongoDB con estructura multi-proyecto.

    Estructura:
    {
        '_id': 'gdc_multi_project',
        'projects': [
            {
                'project_id': 'TCGA-LGG',
                'disease_type': '...',
                'primary_site': '...',
                'data_category': '...',
                'cases': [...]
            },
            {
                'project_id': 'TCGA-GBM',
                ...
            }
        ]
    }

    Args:
        project_documents: Lista de documentos de proyecto individuales

    Returns:
        Documento MongoDB multi-proyecto
    """
    # Remove _id from individual project documents (they'll be nested in projects array)
    projects = []
    for doc in project_documents:
        project_doc = {k: v for k, v in doc.items() if k != '_id'}
        projects.append(project_doc)

    multi_doc = {
        '_id': 'gdc_multi_project',
        'projects': projects
    }

    return multi_doc


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


def save_document_as_json(
    document: Dict[str, Any],
    output_path: str,
    verbose: bool = True
) -> bool:
    """
    Guarda el documento como archivo JSON (sin insertar en MongoDB).

    Args:
        document: Documento a guardar
        output_path: Ruta donde guardar el archivo JSON
        verbose: Si True, muestra información detallada

    Returns:
        True si el guardado fue exitoso, False en caso contrario
    """
    try:
        if verbose:
            print(f"\n[Guardado JSON] Guardando documento como JSON...")

        # Crear directorio si no existe
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Guardar como JSON
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(document, f, indent=2, ensure_ascii=False)

        if verbose:
            file_size = output_file.stat().st_size
            file_size_mb = file_size / (1024 * 1024)
            print(f"[Guardado JSON] Documento guardado exitosamente")
            print(f"  - Archivo: {output_path}")
            print(f"  - Tamaño: {file_size_mb:.2f} MB ({file_size:,} bytes)")

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
    save_as_json: Optional[str] = None,
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
        save_as_json: Ruta donde guardar la colección como JSON (None = no guardar)
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
            print("¡Importación de GDC completada con éxito!")

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
        sys.exit(1)


def run_import(
    gdc_config: 'GDCMongoDataConfig',
    mongo_uri: str,
    database_name: str,
    collection_name: str,
    insert_into_mongodb: bool = True,
    process_expression: bool = False,
    max_files: Optional[int] = None,
    drop_collection: bool = False,
    save_as_json: Optional[str] = None,
    verbose: bool = True
) -> None:
    """
    Función principal que orquesta todo el proceso de importación multi-proyecto.

    Multi-project support: Procesa todos los proyectos configurados y los combina
    en un único documento MongoDB con estructura de array de proyectos.

    Args:
        gdc_config: Configuración GDC con lista de proyectos
        mongo_uri: URI de MongoDB
        database_name: Nombre de la base de datos
        collection_name: Nombre de la colección
        insert_into_mongodb: Si True, inserta en MongoDB; si False, solo genera JSON
        process_expression: Si True, procesa ficheros STAR-Counts
        max_files: Máximo número de ficheros a procesar por proyecto (None = todos)
        drop_collection: Si True, elimina la colección antes de insertar
        save_as_json: Ruta donde guardar el documento como JSON
        verbose: Si True, muestra información detallada
    """
    if verbose:
        print("=" * 100)
        print("IMPORTADOR GDC MULTI-PROYECTO A MONGODB")
        print("=" * 100)
        print(f"\nProcesando {len(gdc_config.projects)} proyecto(s):")
        for proj in gdc_config.projects:
            print(f"  - {proj.project_id}: {proj.disease_type}")
        print("=" * 100)

    project_documents = []

    # Process each project
    for project_idx, project_meta in enumerate(gdc_config.projects, 1):
        if verbose:
            print(f"\n{'=' * 100}")
            print(f"PROCESANDO PROYECTO {project_idx}/{len(gdc_config.projects)}: {project_meta.project_id}")
            print(f"{'=' * 100}")

        try:
            # Build project-specific file paths
            base_dir = Path(gdc_config.base_data_dir).expanduser().resolve()
            project_dir = base_dir / project_meta.project_id

            # Replace {project_id_lower} in filename patterns
            project_id_lower = project_meta.project_id.lower().replace("-", "_")
            manifest_filename = gdc_config.manifest_filename.replace("{project_id_lower}", project_id_lower)
            metadata_filename = gdc_config.metadata_filename.replace("{project_id_lower}", project_id_lower)
            genes_filename = gdc_config.genes_filename.replace("{project_id_lower}", project_id_lower)

            manifest_path = project_dir / manifest_filename
            metadata_path = project_dir / metadata_filename
            genes_path = project_dir / genes_filename
            star_counts_dir = project_dir / gdc_config.star_counts_dirname

            if verbose:
                print(f"\n[1/3] Cargando ficheros TSV para {project_meta.project_id}...")
                print(f"  - Manifest: {manifest_path}")
                print(f"  - Metadata: {metadata_path}")
                print(f"  - Genes: {genes_path}")
                print(f"  - Star counts: {star_counts_dir}")

            # Verify files exist
            if not manifest_path.exists():
                raise FileNotFoundError(f"Manifest no encontrado: {manifest_path}")
            if not metadata_path.exists():
                raise FileNotFoundError(f"Metadata no encontrado: {metadata_path}")
            if not genes_path.exists():
                raise FileNotFoundError(f"Genes no encontrado: {genes_path}")

            # Load TSV files
            manifest_df = load_manifest(str(manifest_path))
            if verbose:
                print(f"  ✓ Manifest cargado: {len(manifest_df)} ficheros")

            metadata_df = load_file_metadata(str(metadata_path))
            if verbose:
                print(f"  ✓ Metadata cargado: {len(metadata_df)} relaciones caso-fichero")

            genes_df = load_genes_table(str(genes_path))
            if not genes_df.empty and verbose:
                print(f"  ✓ Genes cargados: {len(genes_df)} genes")

            # Build project document
            if verbose:
                print(f"\n[2/3] Construyendo documento MongoDB para {project_meta.project_id}...")

            project_doc = build_gdc_document(
                manifest_df=manifest_df,
                metadata_df=metadata_df,
                project_id=project_meta.project_id,
                disease_type=project_meta.disease_type,
                primary_site=project_meta.primary_site,
                data_category=project_meta.data_category,
                star_counts_dir=str(star_counts_dir) if process_expression else None,
                process_expression=process_expression,
                max_files=max_files,
                verbose=verbose
            )

            project_documents.append(project_doc)

            if verbose:
                print(f"  ✓ Documento construido para {project_meta.project_id}")

        except Exception as e:
            print(f"\n✗ ERROR procesando proyecto {project_meta.project_id}: {e}")
            raise

    # Build multi-project document
    if verbose:
        print(f"\n{'=' * 100}")
        print(f"[3/3] Construyendo documento multi-proyecto...")
        print(f"{'=' * 100}")

    multi_doc = build_multi_project_document(project_documents)

    if verbose:
        total_cases = sum(len(proj.get('cases', [])) for proj in multi_doc['projects'])
        print(f"\n  ✓ Documento multi-proyecto construido:")
        print(f"    - Total proyectos: {len(multi_doc['projects'])}")
        print(f"    - Total casos: {total_cases}")

    # Handle insert_into_mongodb flag
    if not insert_into_mongodb:
        if verbose:
            print(f"\n{'=' * 100}")
            print("MODO SOLO JSON: No insertando en MongoDB...")
            print(f"{'=' * 100}")

        if not save_as_json:
            # Generate default output path
            save_as_json = "gdc_multi_project_export.json"

        save_document_as_json(
            document=multi_doc,
            output_path=save_as_json,
            verbose=verbose
        )

        if verbose:
            print(f"\n{'=' * 100}")
            print("✓ PROCESO COMPLETADO EXITOSAMENTE (sin inserción en MongoDB)")
            print(f"{'=' * 100}")
    else:
        # Insert to MongoDB
        if verbose:
            print(f"\n{'=' * 100}")
            print("INSERTANDO EN MONGODB...")
            print(f"{'=' * 100}")

        insert_to_mongo(
            document=multi_doc,
            mongo_uri=mongo_uri,
            database_name=database_name,
            collection_name=collection_name,
            drop_collection=drop_collection,
            save_as_json=save_as_json,
            verbose=verbose
        )

        if verbose:
            print(f"\n{'=' * 100}")
            print("✓ PROCESO COMPLETADO EXITOSAMENTE")
            print(f"{'=' * 100}")
