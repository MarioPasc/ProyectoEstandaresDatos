"""
import_gdc_mongo.py

Importador de datos GDC a MongoDB.
Construye una colección con estructura jerárquica:
  Proyecto → Casos → Ficheros (con expression_summary)

Issue: T1 - GDC MongoDB Import Task
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

import pandas as pd
import numpy as np
from pymongo import MongoClient


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
        file_doc = {
            'file_id': str(file_data.get('file_id', '')),
            'file_name': str(file_data.get('file_name', '')),
            'file_size': int(file_data.get('file_size', 0)) if file_data.get('file_size') else None,
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


def insert_to_mongo(
    document: Dict[str, Any],
    mongo_uri: str,
    database_name: str,
    collection_name: str,
    drop_collection: bool = False,
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

    except Exception as e:
        print(f"Error durante la inserción en MongoDB: {e}")
        sys.exit(1)


def run_import(
    manifest_path: str,
    metadata_path: str,
    genes_path: str,
    project_id: str,
    disease_type: str,
    primary_site: str,
    data_category: str,
    mongo_uri: str,
    database_name: str,
    collection_name: str,
    star_counts_dir: Optional[str] = None,
    process_expression: bool = False,
    max_files: Optional[int] = None,
    drop_collection: bool = False,
    verbose: bool = True
) -> None:
    """
    Función principal que orquesta todo el proceso de importación.

    Esta función es llamada desde gdc_config.py con los parámetros de configuración.
    """
    if verbose:
        print("=" * 60)
        print("IMPORTADOR GDC A MONGODB")
        print("=" * 60)

    # 1. Cargar ficheros TSV
    if verbose:
        print("\n[1/3] Cargando ficheros TSV...")

    manifest_df = load_manifest(manifest_path)
    if verbose:
        print(f"  - Manifest cargado: {len(manifest_df)} ficheros")

    metadata_df = load_file_metadata(metadata_path)
    if verbose:
        print(f"  - Metadata cargado: {len(metadata_df)} relaciones caso-fichero")

    genes_df = load_genes_table(genes_path)
    if not genes_df.empty and verbose:
        print(f"  - Genes cargados: {len(genes_df)} genes")

    # 2. Construir documento MongoDB
    if verbose:
        print("\n[2/3] Construyendo documento MongoDB...")

    document = build_gdc_document(
        manifest_df=manifest_df,
        metadata_df=metadata_df,
        project_id=project_id,
        disease_type=disease_type,
        primary_site=primary_site,
        data_category=data_category,
        star_counts_dir=star_counts_dir,
        process_expression=process_expression,
        max_files=max_files,
        verbose=verbose
    )

    # 3. Insertar en MongoDB
    if verbose:
        print("\n[3/3] Insertando en MongoDB...")

    insert_to_mongo(
        document=document,
        mongo_uri=mongo_uri,
        database_name=database_name,
        collection_name=collection_name,
        drop_collection=drop_collection,
        verbose=verbose
    )

    if verbose:
        print("\n" + "=" * 60)
        print("PROCESO COMPLETADO")
        print("=" * 60)
