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
        - num_rows: número de filas (excluyendo cabecera)
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
            
            # Primera línea como cabecera
            header = lines[0].strip()
            if header:
                result["has_header"] = True
                result["columns"] = header.split("\t")
                result["num_columns"] = len(result["columns"])
            
            # Contar filas de datos (sin incluir cabecera)
            result["num_rows"] = len(lines) - 1 if result["has_header"] else len(lines)
            
    except Exception as e:
        logger.error(f"Error al analizar el archivo {file_path}: {e}")
    
    return result


def check_gdc_files(
    manifest_path: str | Path,
    file_metadata_path: str | Path,
    genes_path: str | Path,
) -> Dict[str, Dict[str, Any]]:
    """
    Verifica y analiza los archivos descargados del GDC.

    Esta función analiza tres tipos de archivos generados por el entrypoint de GDC:
    1. Manifest: archivo de manifiesto tipo GDC Data Transfer Tool
    2. File Metadata: metadatos fichero-caso-muestra
    3. Genes: tabla mínima de genes (symbol ↔ Ensembl gene_id)

    Parameters
    ----------
    manifest_path : str | Path
        Ruta al archivo manifest TSV.
    file_metadata_path : str | Path
        Ruta al archivo de metadatos de ficheros TSV.
    genes_path : str | Path
        Ruta al archivo de genes TSV.

    Returns
    -------
    Dict[str, Dict[str, Any]]
        Diccionario con las estadísticas de cada archivo:
        - manifest: estadísticas del manifest
        - file_metadata: estadísticas de metadatos de ficheros
        - genes: estadísticas de la tabla de genes
    """
    logger.info("=== Verificando archivos descargados del GDC ===")
    
    manifest_path = Path(manifest_path)
    file_metadata_path = Path(file_metadata_path)
    genes_path = Path(genes_path)
    
    results = {
        "manifest": analyze_tsv_file(manifest_path),
        "file_metadata": analyze_tsv_file(file_metadata_path),
        "genes": analyze_tsv_file(genes_path),
    }
    
    # Imprimir resumen
    print("\n" + "=" * 80)
    print("RESUMEN DE ARCHIVOS DESCARGADOS DEL GDC")
    print("=" * 80)
    
    for file_type, stats in results.items():
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
    
    # Validar genes
    genes = results["genes"]
    if genes["exists"]:
        expected_genes_cols = ["symbol", "gene_id"]
        has_expected_cols = all(col in genes["columns"] for col in expected_genes_cols)
        
        if has_expected_cols:
            print(f"   ✓ Tabla de genes tiene las columnas esperadas (symbol, gene_id)")
        else:
            print(f"   ⚠ Tabla de genes no tiene las columnas esperadas")
        
        if genes["num_rows"] > 0:
            print(f"   ✓ Tabla de genes contiene {genes['num_rows']} genes")
        else:
            print(f"   ⚠ Tabla de genes no contiene genes")
    else:
        print(f"   ✗ Tabla de genes no existe")
    
    # Validar consistencia entre archivos
    if manifest["exists"] and file_metadata["exists"]:
        if manifest["num_rows"] == file_metadata["num_rows"]:
            print(f"   ✓ Consistencia: Manifest y file_metadata tienen el mismo número de registros")
        else:
            print(f"   ⚠ Inconsistencia: Manifest ({manifest['num_rows']}) y file_metadata ({file_metadata['num_rows']}) tienen diferente número de registros")


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
