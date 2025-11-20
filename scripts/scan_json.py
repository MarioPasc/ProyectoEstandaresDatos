import os
import json
import csv

# Función para cargar un archivo JSON
def load_json(file_path):
    with open(file_path, 'r') as f:
        return json.load(f)

# Función para contar niveles de anidamiento
def count_levels(data, level=1):
    if isinstance(data, dict):
        return max(count_levels(v, level + 1) for v in data.values()) if data else level
    elif isinstance(data, list):
        return max(count_levels(i, level + 1) for i in data) if data else level
    else:
        return level

# Función para verificar conexiones entre JSONs
def check_connections(json_1, json_2, key_1, key_2):
    connections = []
    for item_1 in json_1:
        for item_2 in json_2:
            if key_1 in item_1 and key_2 in item_2 and item_1[key_1] == item_2[key_2]:
                connections.append((item_1, item_2))
    return connections

# Función principal para realizar el escaneo
def scan_jsons(data_dir):
    # Cargar los archivos JSON
    uniprot_file = os.path.join(data_dir, 'uniprot_collection_export.json')
    gdc_file = os.path.join(data_dir, 'gdc_collection_export.json')
    hgnc_file = os.path.join(data_dir, 'hgnc_collection_export.json')

    uniprot_data = load_json(uniprot_file)
    gdc_data = load_json(gdc_file)
    hgnc_data = load_json(hgnc_file)

    # Verificar niveles de anidamiento
    uniprot_levels = count_levels(uniprot_data)
    gdc_levels = count_levels(gdc_data)
    hgnc_levels = count_levels(hgnc_data)

    # Verificar conexiones entre los tres JSONs
    connections_uniprot_hgnc = check_connections(uniprot_data['uniprot_entries'], hgnc_data, 'uniprot_id', 'uniprot_ids')
    connections_gdc_hgnc = check_connections(gdc_data['projects'], hgnc_data, 'hgnc_ids', 'hgnc_id')
    connections_gdc_uniprot = check_connections(gdc_data['projects'], uniprot_data['uniprot_entries'], 'uniprot_id', 'uniprot_id')

    # Generar el informe en CSV
    with open('json_scan_report.csv', 'w', newline='') as csvfile:
        fieldnames = ['JSON File', 'Levels of Nesting', 'Connections Found']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        writer.writerow({'JSON File': 'UniProt', 'Levels of Nesting': uniprot_levels, 'Connections Found': len(connections_uniprot_hgnc)})
        writer.writerow({'JSON File': 'GDC', 'Levels of Nesting': gdc_levels, 'Connections Found': len(connections_gdc_hgnc)})
        writer.writerow({'JSON File': 'HGNC', 'Levels of Nesting': hgnc_levels, 'Connections Found': len(connections_gdc_uniprot)})

    print("Informe generado: 'json_scan_report.csv'")

# Ejecutar el script
scan_jsons('/path/to/data')
