#!/usr/bin/env python3
"""
Script de ejemplo para verificar archivos descargados manualmente.

Este script puede ejecutarse de forma independiente para verificar
archivos ya descargados sin necesidad de volver a descargarlos.
"""

from pathlib import Path
from DataStandards.utils.check_downloaded_filelength import (
    check_gdc_files,
    check_hgnc_files,
    check_uniprot_files,
)


def main():
    """Ejemplo de uso del verificador de archivos."""
    
    print("=== Verificador de Archivos Descargados ===\n")
    
    # Verificar archivos GDC
    print("1. Verificando archivos GDC...")
    try:
        gdc_results = check_gdc_files(
            manifest_path="data/gdc_manifest_tcga_lgg.tsv",
            file_metadata_path="data/gdc_file_metadata_tcga_lgg.tsv",
            genes_path="data/gdc_genes_tcga_lgg_example.tsv",
        )
    except Exception as e:
        print(f"   Error: {e}\n")
    
    # Verificar archivo HGNC (si existe)
    print("\n2. Verificando archivo HGNC...")
    hgnc_path = Path("data/hgnc_complete_set.tsv")
    if hgnc_path.exists():
        try:
            hgnc_results = check_hgnc_files(hgnc_path)
        except Exception as e:
            print(f"   Error: {e}\n")
    else:
        print(f"   Archivo HGNC no encontrado: {hgnc_path}\n")
    
    # Verificar archivo UniProt (si existe)
    print("\n3. Verificando archivo UniProt...")
    uniprot_path = Path("data/uniprot_human_reviewed.tsv")
    if uniprot_path.exists():
        try:
            uniprot_results = check_uniprot_files(uniprot_path)
        except Exception as e:
            print(f"   Error: {e}\n")
    else:
        print(f"   Archivo UniProt no encontrado: {uniprot_path}\n")
    
    print("\n=== Verificación completada ===")


if __name__ == "__main__":
    main()
