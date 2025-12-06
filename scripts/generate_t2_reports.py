import json
import sys
import os
from pathlib import Path

# Añadir directorio raíz al path para poder importar 'biointegrate'
sys.path.append(str(Path(__file__).resolve().parent.parent))

from biointegrate.t2.transform import json_to_xml, save_xml, apply_xslt

def process_single_file(json_path, xslt_path, output_name):
    """Procesa un solo archivo JSON -> XML -> HTML"""
    print(f"\n Procesando: {json_path.name}")
    
    # Directorio de salida
    results_dir = Path("docs/t2-resultados/t2_final_reports")
    results_dir.mkdir(parents=True, exist_ok=True)
    
    xml_out = results_dir / f"{output_name}.xml"
    html_out = results_dir / f"{output_name}.html"

    try:
        # 1. Cargar JSON
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 2. Transformar a XML
        # Importante: root_tag="results" para que coincida con el XSLT
        tree = json_to_xml(data, root_tag="results")
        save_xml(tree, xml_out)
        print(f"  ✓ XML generado: {xml_out.name}")
        
        # 3. Aplicar XSLT
        apply_xslt(xml_out, xslt_path, html_out)
        print(f"   HTML generado: {html_out}")
        
    except Exception as e:
        print(f"   Error: {e}")
        # import traceback; traceback.print_exc()

def main():
    # --- CONFIGURACIÓN DE RUTAS ---
    # Ruta donde están tus JSONs (la que me pasaste)
    base_json_dir = Path(r"C:\Users\jismbs\Documents\ProyectoEstandaresDatos\docs\t2-resultados")
    
    # Ruta a la plantilla XSLT Universal
    xslt_path = Path("xslt/biointegrate_report.xslt")
    
    # Mapa de archivos a procesar: Nombre del JSON -> Nombre del Reporte Salida
    files_map = {
        "query_1_lgg_uniprot.json": "1_Reporte_LGG_Expression",
        "query_2_completa.json": "2_Reporte_Biomarcadores_Waterfall_v2", 
        "query_3_coverage_cancer_membrane.json": "3_Reporte_Cobertura_Membrana"
    }

    print("=== Generador de Reportes T2 (Multi-Query) ===")
    
    if not xslt_path.exists():
        print(f" Error: No se encuentra la plantilla XSLT en {xslt_path}")
        return

    # Iterar y procesar
    found_any = False
    for json_filename, output_name in files_map.items():
        json_full_path = base_json_dir / json_filename
        
        if json_full_path.exists():
            found_any = True
            process_single_file(json_full_path, xslt_path, output_name)
        else:
            # Intentar buscar en la carpeta docs/t2-queries-ejemplos/results por si acaso
            alt_path = Path(r"C:\Users\jismbs\Documents\ProyectoEstandaresDatos\docs\t2-queries-ejemplos\results") / json_filename
            if alt_path.exists():
                found_any = True
                process_single_file(alt_path, xslt_path, output_name)
            else:
                print(f" Aviso: No se encuentra {json_filename}")

    if found_any:
        print("\n ¡Proceso finalizado! Revisa la carpeta 'results/t2_final_reports'.")
    else:
        print("\n No se procesó ningún archivo. Verifica las rutas en el script.")

if __name__ == "__main__":
    main()