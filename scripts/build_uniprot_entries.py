import argparse
import json
import os
import math

import pandas as pd
import yaml


def load_config(config_path: str) -> dict:
    """Carga el YAML de configuración de datos."""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _none_if_nan(value):
    """Devuelve None si el valor es NaN (pandas/numpy), en otro caso lo deja igual."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _split_field(value, sep=";"):
    """Divide un campo de TSV en lista, manejando NaN y vacíos."""
    value = _none_if_nan(value)
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    parts = [p.strip() for p in text.split(sep)]
    return [p for p in parts if p]


def _bool_from_reviewed(value) -> bool:
    """Convierte la columna 'reviewed' de UniProt a booleano."""
    value = _none_if_nan(value)
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"reviewed", "true", "yes", "1"}


def build_uniprot_docs(mapping_path: str, metadata_path: str, project_id: str = "TCGA-LGG"):
    """
    Construye documentos UniProt (uniprot_entries) a partir de:
      - uniprot_mapping_tcga_<PROJECT>.tsv
      - uniprot_metadata_tcga_<PROJECT>.tsv
    """
    # Mapping: ensembl_gene_id, hgnc_id, symbol, uniprot_id
    map_df = pd.read_csv(mapping_path, sep="\t", dtype=str)
    expected_cols = {"ensembl_gene_id", "hgnc_id", "symbol", "uniprot_id"}
    missing = expected_cols - set(map_df.columns)
    if missing:
        raise ValueError(f"Faltan columnas en mapping TSV: {missing}")
    map_df["project_id"] = project_id

    # Metadata, indexada por Entry (accesión UniProt)
    meta_df = pd.read_csv(metadata_path, sep="\t", dtype=str)
    if "Entry" not in meta_df.columns:
        raise ValueError("El TSV de metadata debe tener una columna 'Entry'.")
    meta_df = meta_df.drop_duplicates(subset=["Entry"]).set_index("Entry")

    docs = []

    # Group by uniprot_id (basic document unit)
    for uniprot_id, group in map_df.groupby("uniprot_id"):
        all_hgnc_ids = sorted({v for v in group["hgnc_id"].dropna().unique() if v})
        all_ensembl_ids = sorted({v for v in group["ensembl_gene_id"].dropna().unique() if v})
        symbols = sorted({v for v in group["symbol"].dropna().unique() if v})

        # Bloque projects.<PROJECT>
        projects = {}
        for proj, proj_group in group.groupby("project_id"):
            proj_hgnc = sorted({v for v in proj_group["hgnc_id"].dropna().unique() if v})
            proj_ens = sorted({v for v in proj_group["ensembl_gene_id"].dropna().unique() if v})
            projects[proj] = {
                "present_in_mapping": True,
                "hgnc_ids": proj_hgnc,
                "ensembl_gene_ids": proj_ens,
                # En el futuro se podrían añadir hgnc_documents / summary_from_hgnc
            }

        # Metadata para este uniprot_id (puede no existir)
        meta = meta_df.loc[uniprot_id] if uniprot_id in meta_df.index else None

        if meta is not None:
            entry_name = _none_if_nan(meta.get("Entry Name"))
            reviewed = _bool_from_reviewed(meta.get("Reviewed"))
            gene_primary = _none_if_nan(meta.get("Gene Names (primary)"))
            gene_synonyms = _split_field(meta.get("Gene Names"), sep=" ")
            org_tax_id = _none_if_nan(meta.get("Organism (ID)"))
            protein_names = _none_if_nan(meta.get("Protein names"))
            length = _none_if_nan(meta.get("Length"))
            protein_existence = _none_if_nan(meta.get("Protein existence"))
            go_mf = _split_field(meta.get("Gene Ontology (molecular function)"), sep=";")
            go_bp = _split_field(meta.get("Gene Ontology (biological process)"), sep=";")
            go_cc = _split_field(meta.get("Gene Ontology (cellular component)"), sep=";")
            raw_cc_function = meta.get("Function [CC]")
            cc_function = _none_if_nan(raw_cc_function)
            cc_subcellular = _split_field(meta.get("Subcellular location [CC]"), sep=";")
        else:
            # Fallback mínimo si el mapping tiene entradas sin metadata
            entry_name = None
            reviewed = False
            gene_primary = symbols[0] if symbols else None
            gene_synonyms = symbols[1:] if len(symbols) > 1 else []
            org_tax_id = None
            protein_names = None
            length = None
            protein_existence = None
            go_mf = []
            go_bp = []
            go_cc = []
            cc_function = None
            cc_subcellular = []

        doc = {
            "_id": uniprot_id,
            "uniprot_id": uniprot_id,
            "entry_name": entry_name,
            "reviewed": reviewed,
            "organism": {
                "taxonomy_id": int(org_tax_id) if org_tax_id and str(org_tax_id).isdigit() else org_tax_id,
                "name": "Homo sapiens" if org_tax_id == "9606" else None,
            },
            "gene": {
                "primary_symbol": gene_primary or (symbols[0] if symbols else None),
                "synonyms": gene_synonyms or symbols,
                "hgnc_ids": all_hgnc_ids,
                "ensembl_gene_ids": all_ensembl_ids,
            },
            "protein": {
                "names": (
                    [protein_names]
                    if protein_names and ";" not in str(protein_names)
                    else _split_field(protein_names, sep=";")
                ),
                "length": int(length) if length and str(length).isdigit() else length,
                "existence_evidence": protein_existence,
                "function_cc": cc_function,
                "subcellular_location_cc": cc_subcellular,
            },
            "go_terms": {
                "molecular_function": go_mf,
                "biological_process": go_bp,
                "cellular_component": go_cc,
            },
            "projects": projects,
        }

        docs.append(doc)

    return docs


def main():
    parser = argparse.ArgumentParser(
        description="Construir documentos UniProt (uniprot_entries) a partir de TSV de mapping y metadata."
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Ruta al YAML de datos (p.ej. config/data/ainhoa_data_config.yaml)",
    )
    parser.add_argument(
        "--project-id",
        default="TCGA-LGG",
        help="Identificador de proyecto GDC (por defecto TCGA-LGG).",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Ruta de salida del JSON. Si se omite, se crea junto al mapping TSV.",
    )

    args = parser.parse_args()
    cfg = load_config(args.config)

    mapping_path = cfg["uniprot"]["mapping_output"]
    metadata_path = cfg["uniprot"]["metadata_output"]

    docs = build_uniprot_docs(mapping_path, metadata_path, project_id=args.project_id)

    if args.output_json is None:
        base_dir = os.path.dirname(mapping_path)
        args.output_json = os.path.join(
            base_dir, f"uniprot_entries_{args.project_id.lower()}.json"
        )

    os.makedirs(os.path.dirname(args.output_json), exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump({"uniprot_entries": docs}, f, ensure_ascii=False, indent=2)

    print(f"Generados {len(docs)} documentos UniProt en: {args.output_json}")


if __name__ == "__main__":
    main()
