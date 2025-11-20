import argparse
import json
import os
import glob
import math
import pandas as pd
import yaml

# --- FUNCIONES AUXILIARES ---

def load_config(config_path: str) -> dict:
    """Carga el YAML de configuración."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"No encuentro el fichero de config: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def _none_if_nan(value):
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

# --- LÓGICA GDC ---

def get_gdc_active_genes(base_dir: str, project_id: str, rnaseq_cfg: dict) -> set:
    """
    Identifica qué genes (Ensembl IDs) existen realmente en los ficheros de GDC.
    Lee SOLO UN fichero de star_counts para ser eficiente.
    """
    # Ruta: data/gdc/TCGA-LGG/star_counts
    star_counts_dir = os.path.join(base_dir, project_id, "star_counts")
    
    # Búsqueda robusta de ficheros .tsv
    files = glob.glob(os.path.join(star_counts_dir, "*.tsv"))
    if not files:
        files = glob.glob(os.path.join(star_counts_dir, "**", "*.tsv"), recursive=True)
    
    if not files:
        print(f"   [WARN] No se encontraron ficheros .tsv en {star_counts_dir}")
        return set()

    sample_file = files[0]
    print(f"   > Usando plantilla de genes: {os.path.basename(sample_file)}")

    # Configuración de columnas desde el YAML
    col_idx = rnaseq_cfg.get('gene_id_column_index', 0)
    strip_ver = rnaseq_cfg.get('strip_version', True)
    
    active_genes = set()
    try:
        with open(sample_file, 'r') as f:
            for line in f:
                parts = line.split()
                if len(parts) <= col_idx: continue
                
                gene_raw = parts[col_idx]
                # Ignorar métricas de STAR (N_unmapped, etc.)
                if gene_raw.startswith("N_"): continue
                
                if strip_ver:
                    # ENSG00000121410.8 -> ENSG00000121410
                    active_genes.add(gene_raw.split('.')[0])
                else:
                    active_genes.add(gene_raw)
    except Exception as e:
        raise RuntimeError(f"Error leyendo fichero GDC: {e}")
            
    return active_genes

def get_project_metadata_payload(base_dir: str, project_id: str) -> dict:
    """
    Carga el metadata del proyecto y devuelve el objeto con case_ids y file_ids.
    """
    pid_lower = project_id.lower()
    
    # Intentamos primero con guion bajo (tcga_lgg), que es lo más común en tus datos
    filename_underscore = f"gdc_file_metadata_{pid_lower.replace('-', '_')}.tsv"
    meta_path = os.path.join(base_dir, project_id, filename_underscore)
    
    # Si no existe, probamos con guion medio
    if not os.path.exists(meta_path):
        filename_hyphen = f"gdc_file_metadata_{pid_lower}.tsv"
        meta_path = os.path.join(base_dir, project_id, filename_hyphen)

    if not os.path.exists(meta_path):
        raise FileNotFoundError(f"Metadata no encontrado para {project_id}. Busqué en: {meta_path}")

    print(f"   > Leyendo metadata: {os.path.basename(meta_path)}")
    df = pd.read_csv(meta_path, sep='\t', dtype=str)
    
    # Normalizar columnas a minúsculas
    df.columns = [c.lower() for c in df.columns]
    
    # Buscar columnas dinámicamente
    col_file = next((c for c in df.columns if 'file_id' in c), None)
    col_case = next((c for c in df.columns if 'case_id' in c and 'project' not in c), None)

    if not col_file or not col_case:
        raise ValueError(f"Columnas file_id/case_id no encontradas en {meta_path}")

    cases = sorted(df[col_case].dropna().unique().tolist())
    files = sorted(df[col_file].dropna().unique().tolist())

    return {
        "case_ids": cases,
        "n_cases": len(cases),
        "file_ids": files
    }

def build_hgnc_docs(hgnc_path: str, gdc_config: dict, project_id: str) -> list:
    """Construye la lista de documentos HGNC + GDC Project Data."""
    
    # 1. Cargar HGNC
    print(f"1. Cargando base HGNC desde {os.path.basename(hgnc_path)}...")
    if not os.path.exists(hgnc_path):
        raise FileNotFoundError(f"Fichero HGNC no encontrado: {hgnc_path}")
    
    df_hgnc = pd.read_csv(hgnc_path, sep='\t', dtype=str)
    # Filtrar filas inválidas (sin IDs)
    df_hgnc = df_hgnc.dropna(subset=['hgnc_id', 'ensembl_gene_id'])

    # 2. Obtener Datos GDC
    print(f"2. Analizando datos GDC para {project_id}...")
    base_dir = gdc_config['base_output_dir']
    rnaseq_cfg = gdc_config.get('rnaseq', {})
    
    active_genes = get_gdc_active_genes(base_dir, project_id, rnaseq_cfg)
    project_payload = get_project_metadata_payload(base_dir, project_id)
    
    docs = []
    match_count = 0

    # 3. Construir JSON
    print("3. Cruzando datos...")
    for _, row in df_hgnc.iterrows():
        ens_id = row['ensembl_gene_id'].strip()
        hgnc_id = row['hgnc_id'].strip()
        
        doc = {
            "_id": hgnc_id,
            "hgnc_id": hgnc_id,
            "symbol": row['symbol'],
            "ensembl_gene_id": ens_id,
            "uniprot_ids": _split_field(row['uniprot_ids'], sep="|"),
            "projects": {}
        }

        # Si el gen existe en GDC, le enchufamos los datos del proyecto
        if ens_id in active_genes:
            doc["projects"][project_id] = project_payload
            match_count += 1
        
        docs.append(doc)

    print(f"   > {match_count} genes vinculados a {project_id}.")
    return docs

# --- MAIN ---

def main():
    parser = argparse.ArgumentParser(description="Construcción del JSON HGNC con mapeo GDC.")
    parser.add_argument("--config", required=True, help="Ruta al YAML de configuración.")
    parser.add_argument("--project-id", default="TCGA-LGG", help="ID del proyecto GDC.")
    parser.add_argument("--output-json", default=None, help="Ruta de salida (opcional).")

    args = parser.parse_args()
    cfg = load_config(args.config)

    # Rutas del YAML
    hgnc_path = cfg["hgnc"]["output_path"]
    
    try:
        docs = build_hgnc_docs(hgnc_path, cfg["gdc"], args.project_id)

        # Definir salida automática si no se especifica
        if args.output_json is None:
            # Guardar en data/output/hgnc_dataset_tcga_lgg.json
            base_out = os.path.dirname(hgnc_path) # data/hgnc
            output_dir = os.path.join(os.path.dirname(base_out), "output") # data/output
            os.makedirs(output_dir, exist_ok=True)
            args.output_json = os.path.join(output_dir, f"hgnc_dataset_{args.project_id.lower()}.json")

        # Guardar JSON
        print(f"4. Guardando JSON en: {args.output_json}")
        with open(args.output_json, "w", encoding="utf-8") as f:
            # Estructura de lista raíz o envuelta en clave, según prefieras. 
            # El issue pide una lista de objetos, pero si tus amigas usan clave raíz, adáptalo.
            # Aquí lo dejo como lista pura de objetos (standard JSON array).
            json.dump(docs, f, indent=2) 

        print("--- HECHO ---")

    except Exception as e:
        print(f"\n[ERROR FATAL] {e}")
        exit(1)

if __name__ == "__main__":
    main()