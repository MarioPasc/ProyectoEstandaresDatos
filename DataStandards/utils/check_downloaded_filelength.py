"""
Módulo para verificar y generar estadísticas de los archivos descargados.

Este módulo proporciona funciones para analizar los archivos TSV descargados
desde diferentes fuentes (GDC, HGNC, UniProt) y generar estadísticas útiles
como número de filas, columnas, tamaño del archivo, etc.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def get_file_stats(file_path: Path) -> Dict[str, Any]:
    """
    Obtiene estadísticas básicas de un archivo.

    Parameters
    ----------
    file_path : Path
        Ruta al archivo a analizar.

    Returns
    -------
    Dict[str, Any]
        Diccionario con estadísticas del archivo:
        - exists: bool, si el archivo existe
        - size_bytes: int, tamaño en bytes
        - size_kb: float, tamaño en kilobytes
        - size_mb: float, tamaño en megabytes
    """
    stats = {
        "exists": file_path.exists(),
        "size_bytes": 0,
        "size_kb": 0.0,
        "size_mb": 0.0,
    }

    if stats["exists"]:
        size_bytes = file_path.stat().st_size
        stats["size_bytes"] = size_bytes
        stats["size_kb"] = round(size_bytes / 1024, 2)
        stats["size_mb"] = round(size_bytes / (1024 * 1024), 2)

    return stats


def analyze_tsv_file(file_path: Path) -> Dict[str, Any]:
    """
    Analiza un archivo TSV y extrae estadísticas detalladas.

    Parameters
    ----------
    file_path : Path
        Ruta al archivo TSV a analizar.

    Returns
    -------
    Dict[str, Any]
        Diccionario con estadísticas:
        - file_name: nombre del archivo
        - exists: si el archivo existe
        - size_bytes, size_kb, size_mb: tamaño del archivo
        - num_rows: número de filas (excluyendo cabecera y comentarios)
        - num_columns: número de columnas
        - columns: lista de nombres de columnas
        - has_header: si tiene cabecera
    """
    file_path = Path(file_path)
    stats = get_file_stats(file_path)
    
    result = {
        "file_name": file_path.name,
        **stats,
        "num_rows": 0,
        "num_columns": 0,
        "columns": [],
        "has_header": False,
    }

    if not stats["exists"]:
        logger.warning(f"El archivo no existe: {file_path}")
        return result

    try:
        with file_path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
            
            if not lines:
                logger.warning(f"El archivo está vacío: {file_path}")
                return result
            
            # Buscar la línea de cabecera (primera línea que no es comentario)
            header_idx = 0
            for i, line in enumerate(lines):
                if not line.strip().startswith("#"):
                    header_idx = i
                    break
            
            # Primera línea no comentario como cabecera
            header = lines[header_idx].strip()
            if header:
                result["has_header"] = True
                result["columns"] = header.split("\t")
                result["num_columns"] = len(result["columns"])
            
            # Contar filas de datos (sin incluir cabecera ni comentarios)
            data_lines = [
                line for line in lines[header_idx + 1:]
                if line.strip() and not line.strip().startswith("#")
            ]
            result["num_rows"] = len(data_lines)
            
    except Exception as e:
        logger.error(f"Error al analizar el archivo {file_path}: {e}")
    
    return result


def analyze_star_counts_directory(star_counts_dir: Path) -> Dict[str, Any]:
    """
    Analiza el directorio de archivos STAR-Counts descargados.

    Parameters
    ----------
    star_counts_dir : Path
        Ruta al directorio con los archivos STAR-Counts.

    Returns
    -------
    Dict[str, Any]
        Diccionario con estadísticas:
        - dir_exists: si el directorio existe
        - num_files: número de archivos en el directorio
        - total_size_mb: tamaño total en MB
        - files: lista de estadísticas de cada archivo individual
    """
    result = {
        "dir_exists": star_counts_dir.exists() and star_counts_dir.is_dir(),
        "num_files": 0,
        "total_size_mb": 0.0,
        "files": [],
    }

    if not result["dir_exists"]:
        logger.warning(f"El directorio no existe: {star_counts_dir}")
        return result

    try:
        # Listar todos los archivos .tsv en el directorio
        tsv_files = list(star_counts_dir.glob("*.tsv"))
        result["num_files"] = len(tsv_files)
        
        total_size_bytes = 0
        
        for tsv_file in tsv_files:
            file_stats = analyze_tsv_file(tsv_file)
            result["files"].append(file_stats)
            total_size_bytes += file_stats.get("size_bytes", 0)
        
        result["total_size_mb"] = round(total_size_bytes / (1024 * 1024), 2)
        
    except Exception as e:
        logger.error(f"Error al analizar el directorio {star_counts_dir}: {e}")
    
    return result


def check_gdc_files(
    manifest_path: str | Path,
    file_metadata_path: str | Path,
    genes_path: str | Path,
    project_genes_path: str | Path = "data/gdc_genes_tcga_lgg.tsv",
    star_counts_dir: str | Path = "data/gdc/star_counts",
) -> Dict[str, Dict[str, Any]]:
    """
    Verifica y analiza los archivos descargados del GDC.

    Esta función analiza los archivos generados por el entrypoint de GDC:
    1. Manifest: archivo de manifiesto tipo GDC Data Transfer Tool
    2. File Metadata: metadatos fichero-caso-muestra
    3. Genes: tabla mínima de genes de ejemplo (symbol ↔ Ensembl gene_id)
    4. Project Genes: tabla completa de genes del proyecto extraída de STAR-Counts
    5. STAR-Counts: archivos RNA-seq descargados

    Parameters
    ----------
    manifest_path : str | Path
        Ruta al archivo manifest TSV.
    file_metadata_path : str | Path
        Ruta al archivo de metadatos de ficheros TSV.
    genes_path : str | Path
        Ruta al archivo de genes de ejemplo TSV.
    project_genes_path : str | Path
        Ruta al archivo de genes del proyecto TSV (por defecto: data/gdc_genes_tcga_lgg.tsv).
    star_counts_dir : str | Path
        Ruta al directorio de archivos STAR-Counts descargados (por defecto: data/gdc/star_counts).

    Returns
    -------
    Dict[str, Dict[str, Any]]
        Diccionario con las estadísticas de cada archivo:
        - manifest: estadísticas del manifest
        - file_metadata: estadísticas de metadatos de ficheros
        - genes: estadísticas de la tabla de genes de ejemplo
        - project_genes: estadísticas de la tabla de genes del proyecto
        - star_counts: estadísticas de los archivos STAR-Counts
    """
    logger.info("=== Verificando archivos descargados del GDC ===")
    
    manifest_path = Path(manifest_path)
    file_metadata_path = Path(file_metadata_path)
    genes_path = Path(genes_path)
    project_genes_path = Path(project_genes_path)
    star_counts_dir = Path(star_counts_dir)
    
    results = {
        "manifest": analyze_tsv_file(manifest_path),
        "file_metadata": analyze_tsv_file(file_metadata_path),
        "genes": analyze_tsv_file(genes_path),
        "project_genes": analyze_tsv_file(project_genes_path),
        "star_counts": analyze_star_counts_directory(star_counts_dir),
    }
    
    # Imprimir resumen
    print("\n" + "=" * 80)
    print("RESUMEN DE ARCHIVOS DESCARGADOS DEL GDC")
    print("=" * 80)
    
    for file_type, stats in results.items():
        if file_type == "star_counts":
            # Manejar el directorio de STAR-Counts de forma especial
            print(f"\n📁 DIRECTORIO STAR-COUNTS")
            if stats["dir_exists"]:
                print(f"   ✓ Existe: Sí")
                print(f"   📊 Número de archivos: {stats['num_files']}")
                print(f"   📊 Tamaño total: {stats['total_size_mb']} MB")
                
                if stats["files"]:
                    print(f"\n   Detalles de archivos individuales:")
                    for i, file_stat in enumerate(stats["files"], 1):
                        print(f"   {i}. {file_stat['file_name']}")
                        print(f"      Filas: {file_stat['num_rows']}, Columnas: {file_stat['num_columns']}, Tamaño: {file_stat['size_mb']} MB")
                        if i == 1 and file_stat["columns"]:
                            print(f"      Columnas disponibles: {', '.join(file_stat['columns'][:5])}{'...' if len(file_stat['columns']) > 5 else ''}")
                    # Imprimir los nombres de las columnas al final (son todas comunes)
                    if stats["files"] and stats["files"][0]["columns"]:
                        print(f"\n   🔤 Nombres de columnas comunes en archivos STAR-Counts: {', '.join(stats['files'][0]['columns'])}")
            else:   
                print(f"   ✗ Existe: No")
            continue
        
        print(f"\n📄 {file_type.upper().replace('_', ' ')}")
        print(f"   Archivo: {stats['file_name']}")
        
        if stats["exists"]:
            print(f"   ✓ Existe: Sí")
            print(f"   📊 Tamaño: {stats['size_kb']} KB ({stats['size_mb']} MB)")
            print(f"   📈 Filas: {stats['num_rows']}")
            print(f"   📋 Columnas: {stats['num_columns']}")
            
            if stats["columns"]:
                print(f"   🔤 Nombres de columnas: {', '.join(stats['columns'])}")
        else:
            print(f"   ✗ Existe: No")
    
    print("\n" + "=" * 80)
    
    # Validaciones adicionales
    _validate_gdc_files(results)
    
    logger.info("=== Verificación de archivos GDC completada ===")
    
    return results


def _validate_gdc_files(results: Dict[str, Dict[str, Any]]) -> None:
    """
    Valida que los archivos GDC cumplan con las expectativas mínimas.

    Parameters
    ----------
    results : Dict[str, Dict[str, Any]]
        Resultados del análisis de archivos GDC.
    """
    print("\n🔍 VALIDACIONES:")
    
    # Validar manifest
    manifest = results["manifest"]
    if manifest["exists"]:
        expected_manifest_cols = ["file_id", "file_name", "md5sum", "file_size", "state"]
        has_expected_cols = all(col in manifest["columns"] for col in expected_manifest_cols)
        
        if has_expected_cols:
            print(f"   ✓ Manifest tiene las columnas esperadas")
        else:
            print(f"   ⚠ Manifest no tiene todas las columnas esperadas")
            print(f"     Esperadas: {expected_manifest_cols}")
            print(f"     Encontradas: {manifest['columns']}")
        
        if manifest["num_rows"] > 0:
            print(f"   ✓ Manifest contiene {manifest['num_rows']} archivos")
        else:
            print(f"   ⚠ Manifest no contiene archivos")
    else:
        print(f"   ✗ Manifest no existe")
    
    # Validar file_metadata
    file_metadata = results["file_metadata"]
    if file_metadata["exists"]:
        if file_metadata["num_rows"] > 0:
            print(f"   ✓ File metadata contiene {file_metadata['num_rows']} registros")
        else:
            print(f"   ⚠ File metadata no contiene registros")
        
        # Verificar que tenga columnas relacionadas con casos
        has_case_info = any("case" in col.lower() for col in file_metadata["columns"])
        if has_case_info:
            print(f"   ✓ File metadata contiene información de casos")
        else:
            print(f"   ⚠ File metadata no parece contener información de casos")
    else:
        print(f"   ✗ File metadata no existe")
    
    # Validar genes de ejemplo
    genes = results["genes"]
    if genes["exists"]:
        expected_genes_cols = ["symbol", "gene_id"]
        has_expected_cols = all(col in genes["columns"] for col in expected_genes_cols)
        
        if has_expected_cols:
            print(f"   ✓ Tabla de genes de ejemplo tiene las columnas esperadas (symbol, gene_id)")
        else:
            print(f"   ⚠ Tabla de genes de ejemplo no tiene las columnas esperadas")
        
        if genes["num_rows"] > 0:
            print(f"   ✓ Tabla de genes de ejemplo contiene {genes['num_rows']} genes")
        else:
            print(f"   ⚠ Tabla de genes de ejemplo no contiene genes")
    else:
        print(f"   ✗ Tabla de genes de ejemplo no existe")
    
    # Validar genes del proyecto (nuevo archivo)
    project_genes = results.get("project_genes")
    if project_genes and project_genes["exists"]:
        expected_project_genes_cols = ["ensembl_gene_id_gdc", "ensembl_gene_id"]
        has_expected_cols = all(col in project_genes["columns"] for col in expected_project_genes_cols)
        
        if has_expected_cols:
            print(f"   ✓ Tabla de genes del proyecto tiene las columnas esperadas (ensembl_gene_id_gdc, ensembl_gene_id)")
        else:
            print(f"   ⚠ Tabla de genes del proyecto no tiene las columnas esperadas")
            print(f"     Esperadas: {expected_project_genes_cols}")
            print(f"     Encontradas: {project_genes['columns']}")
        
        if project_genes["num_rows"] > 0:
            print(f"   ✓ Tabla de genes del proyecto contiene {project_genes['num_rows']} genes")
        else:
            print(f"   ⚠ Tabla de genes del proyecto no contiene genes")
    else:
        print(f"   ⚠ Tabla de genes del proyecto no existe")
    
    # Validar archivos STAR-Counts
    star_counts = results.get("star_counts")
    if star_counts and star_counts["dir_exists"]:
        if star_counts["num_files"] > 0:
            print(f"   ✓ Directorio STAR-Counts contiene {star_counts['num_files']} archivos")
            
            # Verificar que todos los archivos tengan las columnas esperadas
            expected_star_cols = ["gene_id", "gene_name", "gene_type"]
            all_have_expected = all(
                all(col in f["columns"] for col in expected_star_cols)
                for f in star_counts["files"]
                if f.get("columns")
            )
            
            if all_have_expected:
                print(f"   ✓ Todos los archivos STAR-Counts tienen las columnas esperadas (gene_id, gene_name, gene_type, ...)")
            else:
                print(f"   ⚠ Algunos archivos STAR-Counts no tienen las columnas esperadas")
        else:
            print(f"   ⚠ Directorio STAR-Counts está vacío")
    else:
        print(f"   ⚠ Directorio STAR-Counts no existe")
    
    # Validar consistencia entre archivos
    if manifest["exists"] and file_metadata["exists"]:
        if manifest["num_rows"] == file_metadata["num_rows"]:
            print(f"   ✓ Consistencia: Manifest y file_metadata tienen el mismo número de registros")
        else:
            print(f"   ⚠ Inconsistencia: Manifest ({manifest['num_rows']}) y file_metadata ({file_metadata['num_rows']}) tienen diferente número de registros")
    
    # Validar que project_genes tenga más genes que el archivo de ejemplo
    if genes["exists"] and project_genes and project_genes["exists"]:
        if project_genes["num_rows"] > genes["num_rows"]:
            print(f"   ✓ Tabla de genes del proyecto ({project_genes['num_rows']}) es más completa que la de ejemplo ({genes['num_rows']})")
        elif project_genes["num_rows"] == genes["num_rows"]:
            print(f"   ⚠ Tabla de genes del proyecto y de ejemplo tienen el mismo tamaño ({genes['num_rows']})")
        else:
            print(f"   ⚠ Tabla de genes del proyecto ({project_genes['num_rows']}) tiene menos genes que la de ejemplo ({genes['num_rows']})")



def check_hgnc_files(hgnc_path: str | Path) -> Dict[str, Any]:
    """
    Verifica y analiza el archivo descargado de HGNC.

    Parameters
    ----------
    hgnc_path : str | Path
        Ruta al archivo HGNC complete set TSV.

    Returns
    -------
    Dict[str, Any]
        Diccionario con las estadísticas del archivo HGNC.
    """
    logger.info("=== Verificando archivo descargado de HGNC ===")
    
    hgnc_path = Path(hgnc_path)
    stats = analyze_tsv_file(hgnc_path)
    
    # Imprimir resumen
    print("\n" + "=" * 80)
    print("RESUMEN DE ARCHIVO DESCARGADO DE HGNC")
    print("=" * 80)
    print(f"\n📄 HGNC COMPLETE SET")
    print(f"   Archivo: {stats['file_name']}")
    
    if stats["exists"]:
        print(f"   ✓ Existe: Sí")
        print(f"   📊 Tamaño: {stats['size_kb']} KB ({stats['size_mb']} MB)")
        print(f"   📈 Filas: {stats['num_rows']}")
        print(f"   📋 Columnas: {stats['num_columns']}")
        
        if stats["columns"] and len(stats["columns"]) <= 10:
            print(f"   🔤 Nombres de columnas: {', '.join(stats['columns'])}")
        elif stats["columns"]:
            print(f"   🔤 Primeras 10 columnas: {', '.join(stats['columns'][:10])}...")
    else:
        print(f"   ✗ Existe: No")
    
    print("\n" + "=" * 80)
    
    logger.info("=== Verificación de archivo HGNC completada ===")
    
    return stats


def check_uniprot_files(uniprot_path: str | Path) -> Dict[str, Any]:
    """
    Verifica y analiza el archivo descargado de UniProt.

    Parameters
    ----------
    uniprot_path : str | Path
        Ruta al archivo UniProt TSV.

    Returns
    -------
    Dict[str, Any]
        Diccionario con las estadísticas del archivo UniProt.
    """
    logger.info("=== Verificando archivo descargado de UniProt ===")
    
    uniprot_path = Path(uniprot_path)
    stats = analyze_tsv_file(uniprot_path)
    
    # Imprimir resumen
    print("\n" + "=" * 80)
    print("RESUMEN DE ARCHIVO DESCARGADO DE UNIPROT")
    print("=" * 80)
    print(f"\n📄 UNIPROT DATA")
    print(f"   Archivo: {stats['file_name']}")
    
    if stats["exists"]:
        print(f"   ✓ Existe: Sí")
        print(f"   📊 Tamaño: {stats['size_kb']} KB ({stats['size_mb']} MB)")
        print(f"   📈 Filas: {stats['num_rows']}")
        print(f"   📋 Columnas: {stats['num_columns']}")
        
        if stats["columns"]:
            print(f"   🔤 Nombres de columnas: {', '.join(stats['columns'])}")
    else:
        print(f"   ✗ Existe: No")
    
    print("\n" + "=" * 80)
    
    logger.info("=== Verificación de archivo UniProt completada ===")
    
    return stats
