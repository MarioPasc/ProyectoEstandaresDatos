import yaml
import pandas as pd
from pymongo import MongoClient, UpdateOne
import sys
import os

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
    """Separa términos GO que vienen como 'Term1 [GO:0001]; Term2 [GO:0002]'."""
    if not isinstance(go_string, str) or not go_string:
        return []
    # Usamos strip() en cada término para limpiar espacios
    return [term.strip() for term in go_string.split(';')]

def process_protein_row(row, mapping_dict):
    """Transforma una fila del DataFrame de UniProt al formato de documento anidado."""
    
    uniprot_id = row.get('Entry')
    if not uniprot_id:
        return None

    # Buscamos la info del gen en el diccionario de mapeo
    gene_info = mapping_dict.get(uniprot_id, [])

    # Construye el documento basado en la Sección 4.4 de T1_README_Datos.md
    document = {
        '_id': uniprot_id,
        'entry_name': row.get('Entry Name'),
        'reviewed': row.get('Reviewed'),
        'protein_existence': row.get('Protein existence'),
        'length': row.get('Length'),
        'organism_id': row.get('Organism (ID)'),
        'protein_names': row.get('Protein names'),

        # Nivel 2: Gen(es) asociados
        'genes': gene_info, # gene_info ya es una lista de dicts

        # Nivel 3: Anotación funcional GO
        'go': {
            'molecular_function': split_go_terms(row.get('Gene Ontology (molecular function)')),
            'biological_process': split_go_terms(row.get('Gene Ontology (biological process)')),
            'cellular_component': split_go_terms(row.get('Gene Ontology (cellular component)'))
        },

        # Nivel 4: Comentarios curados
        'comments': {
            'function': row.get('Function [CC]'),
            'subcellular_location': split_go_terms(row.get('Subcellular location [CC]'))
        }
    }
    return document

def load_mapping_file(mapping_path):
    """
    Carga el fichero de mapeo y lo convierte en un diccionario
    donde cada clave uniprot_id tiene una lista de genes asociados.
    """
    try:
        df_map = pd.read_csv(mapping_path, sep='\t')
        df_map = df_map.fillna(None)
    except FileNotFoundError:
        print(f"Error: No se encuentra el fichero de mapeo de UniProt en {mapping_path}")
        print("Asegúrate de haberlo descargado con 'datastandards-download --source uniprot'")
        sys.exit(1)
        
    mapping_dict = {}
    for _, row in df_map.iterrows():
        uniprot_id = row.get('uniprot_id')
        if not uniprot_id:
            continue
            
        gene_doc = {
            'ensembl_gene_id': row.get('ensembl_gene_id'),
            'hgnc_id': row.get('hgnc_id'),
            'symbol': row.get('symbol')
        }
        
        if uniprot_id not in mapping_dict:
            mapping_dict[uniprot_id] = []
        mapping_dict[uniprot_id].append(gene_doc)
        
    return mapping_dict

def main():
    print("Iniciando importación de UniProt (Proteínas)...")
    
    # 1. Cargar Configuración
    config = load_config('config/data_config.yaml')
    
    # 2. Conectar a MongoDB
    db = connect_db(config)
    collection_name = config['mongodb_T1']['collections']['proteins']
    collection = db[collection_name]
    print(f"Conectado a MongoDB, base: {config['mongodb_T1']['database_name']}, colección: {collection_name}")

    # 3. Cargar el fichero de Mapeo (genes <-> proteínas)
    mapping_path = config['uniprot']['mapping_output']
    print(f"Cargando fichero de mapeo desde {mapping_path}...")
    mapping_dict = load_mapping_file(mapping_path)
    print(f"Se han cargado {len(mapping_dict)} mapeos de proteínas.")

    # 4. Leer fichero TSV de Metadata de UniProt
    metadata_path = config['uniprot']['metadata_output']
    if not os.path.exists(metadata_path):
        print(f"Error: No se encuentra el fichero de metadata de UniProt en {metadata_path}")
        print("Asegúrate de haberlo descargado con 'datastandards-download --source uniprot'")
        sys.exit(1)
        
    print(f"Leyendo fichero TSV de metadata desde {metadata_path}...")
    df_meta = pd.read_csv(metadata_path, sep='\t')
    df_meta = df_meta.fillna(None)
    print(f"Se han leído {len(df_meta)} filas del fichero de metadata de UniProt.")

    # 5. Transformar y preparar operaciones
    operations = []
    for _, row in df_meta.iterrows():
        doc = process_protein_row(row, mapping_dict)
        if doc:
            operations.append(
                UpdateOne({'_id': doc['_id']}, {'$set': doc}, upsert=True)
            )

    # 6. Ejecutar carga masiva (Bulk Write)
    if not operations:
        print("No se generaron operaciones. Comprueba los ficheros TSV.")
        return

    print(f"Preparando carga masiva de {len(operations)} documentos...")
    try:
        result = collection.bulk_write(operations)
        print("\n--- Resultados de la Carga ---")
        print(f"Documentos insertados (nuevos): {result.upserted_count}")
        print(f"Documentos modificados (actualizados): {result.modified_count}")
        print("¡Importación de Proteínas (UniProt) completada con éxito!")
    except Exception as e:
        print(f"Error durante la carga masiva (bulk write): {e}")

if __name__ == "__main__":
    main()