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
    # --- CONFIGURACIÓN DE RUTAS GENÉRICAS ---
    
    # 1. Obtener la raíz del proyecto dinámicamente
    # (El script está en /scripts, así que subimos 2 niveles: scripts -> root)
    project_root = Path(__file__).resolve().parent.parent
    
    # 2. Definir rutas relativas desde la raíz
    base_json_dir = project_root / "docs" / "t2-resultados"
    xslt_path = project_root / "xslt" / "biointegrate_report.xslt"
    
    # Ruta alternativa para buscar JSONs (ejemplos)
    alt_json_dir = project_root / "docs" / "t2-queries-ejemplos" / "results"

    # Mapa de archivos a procesar
    files_map = {
        "query_1_lgg_uniprot.json": "1_Reporte_LGG_Expression",
        "query_2_completa.json": "2_Reporte_Biomarcadores_Waterfall_v2", 
        "query_3_coverage_cancer_membrane.json": "3_Reporte_Cobertura_Membrana"
    }

    print(f"=== Generador de Reportes T2 (Ruta Base: {project_root.name}) ===")
    
    if not xslt_path.exists():
        print(f" Error: No se encuentra la plantilla XSLT en: {xslt_path}")
        return

    # Iterar y procesar
    found_any = False
    for json_filename, output_name in files_map.items():
        # Intentar ruta principal
        json_full_path = base_json_dir / json_filename
        
        if json_full_path.exists():
            found_any = True
            process_single_file(json_full_path, xslt_path, output_name)
        else:
            # Intentar ruta alternativa
            alt_path = alt_json_dir / json_filename
            if alt_path.exists():
                found_any = True
                process_single_file(alt_path, xslt_path, output_name)
            else:
                print(f" Aviso: No se encuentra '{json_filename}' en ninguna de las carpetas de docs/")

    if found_any:
        # Indicar ruta de salida relativa para que sea fácil de leer
        out_rel = (project_root / "results" / "t2_final_reports")
        print(f"\n ¡Proceso finalizado! Revisa la carpeta: {out_rel}")
    else:
        print("\n No se procesó ningún archivo. Verifica que los JSON estén en 'docs/t2-resultados' o 'docs/t2-queries-ejemplos/results'.")

if __name__ == "__main__":
    main()