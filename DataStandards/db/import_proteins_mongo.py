import yaml
import pandas as pd
from pymongo import MongoClient, UpdateOne
import sys
import os
from pathlib import Path
from typing import Dict, List, Any

# --- Funciones de Utilidad ---

def load_config(config_path='config/data_config.yaml'):
    """Carga el fichero de configuración YAML."""
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: Fichero de configuración no encontrado en {config_path}")
        sys.exit(1)
    except Exception as e:
        print(f"Error cargando YAML: {e}")
        sys.exit(1)

def connect_db(config):
    """Se conecta a MongoDB usando la configuración."""
    try:
        client = MongoClient(config['mongodb_T1']['mongo_uri'])
        db = client[config['mongodb_T1']['database_name']]
        return db
    except Exception as e:
        print(f"Error conectando a MongoDB: {e}")
        sys.exit(1)

def split_go_terms(go_string):
    """Separa términos GO (ej: 'Term [GO:0001]; Term2 [GO:0002]') en una lista de strings."""
    if not isinstance(go_string, str) or not go_string:
        return []
    # Usamos strip() en cada término para limpiar espacios
    return [term.strip() for term in go_string.split(';')]

def update_mapping_dict(mapping_dict: Dict, mapping_path: str, current_project_id: str):
    """
    Carga un fichero de mapeo de un proyecto específico y ACTUALIZA el diccionario general.
    
    Args:
        mapping_dict: Diccionario acumulativo (se modifica in-place).
        mapping_path: Ruta al fichero TSV del proyecto actual.
        current_project_id: ID del proyecto actual (ej: TCGA-GBM) para forzar la consistencia.
    """
    try:
        df_map = pd.read_csv(mapping_path, sep='\t')
        df_map = df_map.fillna('')
    except FileNotFoundError:
        print(f"Advertencia: No se encuentra el fichero de mapeo en {mapping_path}. Se omite este proyecto.")
        return

    print(f"   -> Procesando mapeo para {current_project_id}...")

    for _, row in df_map.iterrows():
        uniprot_id = row.get('uniprot_id')
        # Usamos el ID del proyecto actual, o el del fichero si existe
        project_id = current_project_id
        
        if not uniprot_id:
            continue
            
        if uniprot_id not in mapping_dict:
            mapping_dict[uniprot_id] = {
                'primary_symbol': '',
                'hgnc_ids': set(),
                'ensembl_gene_ids': set(),
                'projects': {}
            }
        
        # Agrupar IDs para la sección 'gene' (Globales para la proteína)
        if row.get('hgnc_id'):
            mapping_dict[uniprot_id]['hgnc_ids'].add(row.get('hgnc_id'))
        if row.get('ensembl_gene_id'):
            mapping_dict[uniprot_id]['ensembl_gene_ids'].add(row.get('ensembl_gene_id'))
        if row.get('symbol') and not mapping_dict[uniprot_id]['primary_symbol']:
             mapping_dict[uniprot_id]['primary_symbol'] = row.get('symbol')

        # Agrupar información para la sección 'projects'
        if project_id not in mapping_dict[uniprot_id]['projects']:
            mapping_dict[uniprot_id]['projects'][project_id] = {
                'present_in_mapping': True,
                'hgnc_documents': set(),
                'ensembl_gene_ids': set(),
                'summary_from_hgnc': {
                    'n_cases': 0, # Placeholder
                    'n_files': 0  # Placeholder
                }
            }

        # Actualizar la sección projects con IDs específicos del proyecto
        if row.get('hgnc_id'):
            mapping_dict[uniprot_id]['projects'][project_id]['hgnc_documents'].add(row.get('hgnc_id'))
        if row.get('ensembl_gene_id'):
            mapping_dict[uniprot_id]['projects'][project_id]['ensembl_gene_ids'].add(row.get('ensembl_gene_id'))

# --- Lógica de Transformación (Adaptada a Issue #17) ---

def process_protein_row(row, mapping_dict):
    """Transforma una fila del DataFrame de UniProt (Metadata) al nuevo formato anidado (Issue #17)."""
    
    uniprot_id = row.get('Entry')
    if not uniprot_id:
        return None

    # Recuperar información consolidada del mapeo
    map_data = mapping_dict.get(uniprot_id, {})
    
    # Convertir sets a listas para el documento final
    hgnc_ids_list = list(filter(None, map_data.get('hgnc_ids', [])))
    ensembl_ids_list = list(filter(None, map_data.get('ensembl_gene_ids', [])))
    
    # Procesar proyectos (convertir sets internos a listas)
    projects_data = map_data.get('projects', {})
    for proj_key, proj_val in projects_data.items():
        if isinstance(proj_val.get('hgnc_documents'), set):
            proj_val['hgnc_documents'] = list(filter(None, proj_val['hgnc_documents']))
        if isinstance(proj_val.get('ensembl_gene_ids'), set):
            proj_val['ensembl_gene_ids'] = list(filter(None, proj_val['ensembl_gene_ids']))

    # -------------------------------------------------------------------------
    # 1. CONSTRUCCIÓN DE LA ESTRUCTURA PRINCIPAL (Issue #17)
    # -------------------------------------------------------------------------
    document = {
        '_id': uniprot_id,
        'uniprot_id': uniprot_id,
        'entry_name': row.get('Entry Name'),
        'reviewed': row.get('Reviewed', 'unreviewed') == 'reviewed', 
        
        # Nivel 2: organism
        'organism': {
            'taxonomy_id': row.get('Organism (ID)'),
            'name': "Homo sapiens" 
        },
        
        # Nivel 2: gene (IDs de enlace consolidados)
        'gene': {
            'primary_symbol': map_data.get('primary_symbol', row.get('Gene Names (primary)')),
            'synonyms': list(filter(None, str(row.get('Gene Names', '')).split(' '))), 
            'hgnc_ids': hgnc_ids_list,
            'ensembl_gene_ids': ensembl_ids_list
        },

        # Nivel 2: protein
        'protein': {
            'names': list(filter(None, str(row.get('Protein names', '')).split(';'))), 
            'length': row.get('Length'),
            'existence_evidence': row.get('Protein existence'),
            # Nivel 3: Comentarios curados
            'function_cc': row.get('Function [CC]'),
            'subcellular_location_cc': split_go_terms(row.get('Subcellular location [CC]'))
        },
        
        # Nivel 2: go_terms
        'go_terms': {
            'molecular_function': split_go_terms(row.get('Gene Ontology (molecular function)')),
            'biological_process': split_go_terms(row.get('Gene Ontology (biological process)')),
            'cellular_component': split_go_terms(row.get('Gene Ontology (cellular component)'))
        },
        
        # Nivel 2: projects (Relación HGNC/GDC)
        'projects': projects_data
    }
    
    return document

# --- Función Principal de Orquestación ---

def main():
    print("Iniciando importación de UniProt (Proteínas) - Multi-Project Refactor...")
    
    config = load_config('config/data_config.yaml')
    
    db = connect_db(config)
    collection_name = config['mongodb_T1']['collections'].get('proteins', 'uniprot_entries')
    collection = db[collection_name] 
    print(f"Conectado a MongoDB, base: {config['mongodb_T1']['database_name']}, colección: {collection_name}")

    # --- Lógica de Rutas Dinámicas ---
    # Obtenemos la ruta base de UniProt desde el config, o la inferimos
    # Si el config tiene una ruta completa a un archivo (ej: .../data/uniprot/uniprot_mapping.tsv),
    # usamos .parent para obtener el directorio base (.../data/uniprot)
    yaml_mapping_path = Path(config['uniprot']['mapping_output'])
    uniprot_base_dir = yaml_mapping_path.parent.parent
    
    # Obtenemos la lista de proyectos
    project_ids = config['gdc'].get('project_ids', [])
    # Fallback por si en el YAML sigue como 'project_id' string
    if isinstance(project_ids, str):
        project_ids = [project_ids]
    elif not project_ids and config['gdc'].get('project_id'):
         project_ids = [config['gdc']['project_id']]

    print(f"Proyectos detectados: {project_ids}")
    print(f"Directorio base UniProt: {uniprot_base_dir}")

    # 1. Cargar y consolidar Mapeos de TODOS los proyectos
    mapping_dict = {}
    metadata_files = []

    for pid in project_ids:
        # Construir rutas: .../data/uniprot/{TCGA-PROJECT}/uniprot_mapping_{tcga_project}.tsv
        pid_lower = pid.lower().replace("-", "_")
        project_dir = uniprot_base_dir / pid
        
        mapping_file = project_dir / f"uniprot_mapping_{pid_lower}.tsv"
        metadata_file = project_dir / f"uniprot_metadata_{pid_lower}.tsv"
        
        if mapping_file.exists():
            update_mapping_dict(mapping_dict, str(mapping_file), pid)
        else:
            print(f"Advertencia: No encontrado mapping para {pid} en {mapping_file}")

        if metadata_file.exists():
            metadata_files.append(metadata_file)
        else:
            print(f"Advertencia: No encontrado metadata para {pid} en {metadata_file}")

    print(f"Se han consolidado mapeos para {len(mapping_dict)} proteínas únicas.")

    # 2. Procesar Metadata y Subir a Mongo
    # Procesamos los ficheros de metadata secuencialmente.
    # Usamos un set para no procesar el mismo uniprot_id dos veces si aparece en ambos proyectos con mismos datos.
    processed_uniprot_ids = set()
    operations = []

    for meta_path in metadata_files:
        print(f"Leyendo metadata desde {meta_path}...")
        df_meta = pd.read_csv(meta_path, sep='\t')
        df_meta = df_meta.fillna('')

        for _, row in df_meta.iterrows():
            uid = row.get('Entry')
            if uid in processed_uniprot_ids:
                continue # Ya procesamos esta proteína en otro proyecto
            
            doc = process_protein_row(row, mapping_dict)
            if doc:
                operations.append(
                    UpdateOne({'_id': doc['_id']}, {'$set': doc}, upsert=True)
                )
                processed_uniprot_ids.add(uid)

    # 3. Ejecutar carga masiva
    if not operations:
        print("No se generaron operaciones. Verifica tus ficheros y rutas.")
        return

    print(f"Preparando carga masiva de {len(operations)} documentos...")
    try:
        result = collection.bulk_write(operations)
        print("\n--- Resultados de la Carga ---")
        print(f"Documentos insertados (nuevos): {result.upserted_count}")
        print(f"Documentos modificados (actualizados): {result.modified_count}")
        print(f"¡Importación completada con éxito!")
    except Exception as e:
        print(f"Error durante la carga masiva (bulk write): {e}")

if __name__ == "__main__":
    main()