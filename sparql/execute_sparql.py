import rdflib
import csv
from pathlib import Path

# 1. Detectar la raíz subiendo un nivel desde la carpeta 'sparql'
# Si el script está en .../ProyectoEstandaresDatos/sparql, ROOT es .../ProyectoEstandaresDatos
ROOT_DIR = Path(__file__).resolve().parent.parent

# 2. Rutas relativas corregidas
OWL_FILE = ROOT_DIR / "ontology" / "assets" / "biointegrate-ontology-reasoned.owl"
QUERIES_DIR = ROOT_DIR / "sparql"
OUTPUT_DIR = ROOT_DIR / "results" / "sparql"

def execute_task_t3():
    # Validación de existencia del OWL
    if not OWL_FILE.exists():
        print(f"Error: No se encuentra el archivo OWL en: {OWL_FILE}")
        print(f"Por favor, verifica que la carpeta 'ontology/assets' existe en la raíz.")
        return

    print(f"--- Iniciando ejecución de consultas SPARQL ---")
    print(f"Archivo OWL detectado: {OWL_FILE.name}")
    
    g = rdflib.Graph()
    try:
        g.parse(str(OWL_FILE), format="xml")
        print("✓ Ontología cargada correctamente en memoria.")
    except Exception as e:
        print(f"✗ Error cargando el OWL: {e}")
        return

    # Crear carpeta de resultados
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Procesar consultas de la 2 a la 6
    for i in range(2, 7):
        query_file = f"q0{i}.rq"
        query_path = QUERIES_DIR / query_file
        
        if query_path.exists():
            print(f"Ejecutando {query_file}...")
            with open(query_path, 'r', encoding='utf-8') as f:
                query_str = f.read()
            
            try:
                results = g.query(query_str)
                
                output_file = OUTPUT_DIR / f"q0{i}_results.csv"
                with open(output_file, 'w', newline='', encoding='utf-8') as f_out:
                    writer = csv.writer(f_out)
                    writer.writerow([str(v) for v in results.vars])
                    for row in results:
                        writer.writerow([str(v) for v in row])
                
                print(f"   ✓ Éxito. Guardado en: results/sparql/{output_file.name}")
            except Exception as e:
                print(f"   ✗ Error en {query_file}: {e}")
        else:
            print(f"⚠ Aviso: No se encontró {query_file} en la carpeta sparql/")

if __name__ == "__main__":
    execute_task_t3()