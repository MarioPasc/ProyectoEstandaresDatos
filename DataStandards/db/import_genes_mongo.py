import yaml
import pandas as pd
from pymongo import MongoClient, UpdateOne
import sys
import os

def load_config(config_path='config/data_config.yaml'):
    """Carga el fichero de configuración YAML."""
    try:
        with open(config_path, 'r') as f:
            # Usamos FullLoader para evitar warnings de seguridad
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: Configuration file not found at {config_path}")
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

def process_hgnc_row(row):
    """Transforma una fila del DataFrame de HGNC al formato de documento anidado."""
    
    # Manejar listas que pueden estar como strings (ej. 'ID1|ID2')
    def split_field(value, sep='|'):
        if isinstance(value, str) and value:
            return value.split(sep)
        return []

    # Construye el documento basado en la Sección 3.4 de T1_README_Datos.md
    document = {
        '_id': row.get('hgnc_id'),
        'symbol': row.get('symbol'),
        'name': row.get('name'),
        'locus_group': row.get('locus_group'),
        'locus_type': row.get('locus_type'),
        'status': row.get('status'),
        'location': row.get('location'),

        # Nivel 2: Identificadores
        'identifiers': {
            'ensembl_gene_id': row.get('ensembl_gene_id'),
            'entrez_id': row.get('entrez_id'),
            'refseq_accession': row.get('refseq_accession'),
            'ucsc_id': row.get('ucsc_id')
        },

        # Nivel 2: Sinónimos
        'synonyms': {
            'alias_symbol': split_field(row.get('alias_symbol')),
            'prev_symbol': split_field(row.get('prev_symbol')),
            'alias_name': split_field(row.get('alias_name')),
            'prev_name': split_field(row.get('prev_name'))
        },

        # Nivel 3: Enlaces externos
        'external_links': {
            'uniprot_ids': split_field(row.get('uniprot_ids')),
            'omim_id': split_field(row.get('omim_id')),
            'orphanet': row.get('orphanet'),
            'cosmic': row.get('cosmic')
        }
    }
    return document

def main():
    print("Iniciando importación de HGNC (Genes)...")
    
    # 1. Cargar Configuración
    # Asumimos que el script se corre desde la raíz del proyecto
    config = load_config('config/data_config.yaml')
    
    # 2. Conectar a MongoDB
    db = connect_db(config)
    collection_name = config['mongodb_T1']['collections']['genes']
    collection = db[collection_name]
    print(f"Conectado a MongoDB, base: {config['mongodb_T1']['database_name']}, colección: {collection_name}")

    # 3. Leer fichero TSV de HGNC
    hgnc_path = config['hgnc']['output_path']
    if not os.path.exists(hgnc_path):
        print(f"Error: No se encuentra el fichero de HGNC en {hgnc_path}")
        print("Asegúrate de haberlo descargado con 'datastandards-download --source hgnc'")
        sys.exit(1)
        
    print(f"Leyendo fichero TSV desde {hgnc_path}...")
    # low_memory=False es importante para ficheros grandes con tipos mixtos
    df = pd.read_csv(hgnc_path, sep='\t', low_memory=False)
    
    # Reemplazar NaNs por strings vacíos para evitar problemas con Mongo
    df = df.fillna('')
    print(f"Se han leído {len(df)} filas del fichero HGNC.")

    # 4. Transformar y preparar operaciones
    operations = []
    for _, row in df.iterrows():
        # Saltamos filas que no tengan un hgnc_id
        if not row.get('hgnc_id'):
            continue
            
        doc = process_hgnc_row(row)
        
        # Usamos UpdateOne con upsert=True. 
        # Esto inserta si no existe, o actualiza si ya existe.
        # Es la forma estándar y segura de cargar datos.
        operations.append(
            UpdateOne({'_id': doc['_id']}, {'$set': doc}, upsert=True)
        )

    # 5. Ejecutar carga masiva (Bulk Write)
    if not operations:
        print("No se generaron operaciones. Comprueba el fichero TSV.")
        return

    print(f"Preparando carga masiva de {len(operations)} documentos...")
    try:
        result = collection.bulk_write(operations)
        print("\n--- Resultados de la Carga ---")
        print(f"Documentos insertados (nuevos): {result.upserted_count}")
        print(f"Documentos modificados (actualizados): {result.modified_count}")
        print("¡Importación de Genes (HGNC) completada con éxito!")
    except Exception as e:
        print(f"Error durante la carga masiva (bulk write): {e}")

if __name__ == "__main__":
    main()