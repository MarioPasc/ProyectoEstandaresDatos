"""
evaluate.py

Módulo para evaluación de calidad de los documentos JSON generados por el pipeline.
Verifica estructura, campos requeridos, tipos de datos y genera estadísticas de completitud.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class FieldValidation:
    """Resultado de validación de un campo."""
    field_name: str
    exists: bool
    expected_type: str
    actual_type: str
    is_valid: bool
    message: str = ""


@dataclass
class DocumentStats:
    """Estadísticas de un documento JSON."""
    total_fields: int = 0
    valid_fields: int = 0
    missing_fields: int = 0
    invalid_type_fields: int = 0
    null_fields: int = 0
    empty_collections: int = 0


@dataclass
class QualityReport:
    """Reporte de calidad para un fichero JSON."""
    source: str  # GDC, HGNC, UniProt
    file_path: str
    is_valid: bool = True
    document_count: int = 0
    stats: DocumentStats = field(default_factory=DocumentStats)
    field_validations: list[FieldValidation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    completeness_score: float = 0.0  # Porcentaje de completitud (0-100)

    def add_warning(self, message: str) -> None:
        """Añade un warning al reporte."""
        self.warnings.append(message)
        logger.warning(f"[{self.source}] {message}")

    def add_error(self, message: str) -> None:
        """Añade un error al reporte."""
        self.errors.append(message)
        self.is_valid = False
        logger.error(f"[{self.source}] {message}")

    def calculate_completeness(self) -> None:
        """Calcula el porcentaje de completitud."""
        if self.stats.total_fields > 0:
            self.completeness_score = (
                self.stats.valid_fields / self.stats.total_fields
            ) * 100
        else:
            self.completeness_score = 0.0


# Esquemas de validación para cada fuente de datos
GDC_SCHEMA = {
    "required_fields": {
        "project_id": str,
        "disease_type": str,
        "primary_site": str,
        "cases": list,
    },
    "case_fields": {
        "case_id": str,
        "submitter_id": str,
        "files": list,
    },
    "file_fields": {
        "file_id": str,
        "file_name": str,
    },
}

HGNC_SCHEMA = {
    "required_fields": {
        "hgnc_id": str,
        "symbol": str,
        "name": str,
    },
    "optional_fields": {
        "ensembl_gene_id": (str, type(None)),
        "uniprot_ids": (str, type(None)),
        "projects": dict,
    },
}

UNIPROT_SCHEMA = {
    "required_fields": {
        "uniprot_entries": list,
    },
    "entry_fields": {
        "uniprot_id": str,
        "accession": str,
    },
    "optional_entry_fields": {
        "gene_primary": (str, type(None)),
        "protein_name": (str, type(None)),
        "organism_id": (int, str, type(None)),
        "projects": dict,
    },
}


def validate_field(
    data: dict,
    field_name: str,
    expected_type: type | tuple,
    required: bool = True
) -> FieldValidation:
    """
    Valida un campo de un documento.

    Parameters
    ----------
    data : dict
        Documento a validar.
    field_name : str
        Nombre del campo a validar.
    expected_type : type | tuple
        Tipo(s) esperado(s) para el campo.
    required : bool
        Si el campo es requerido.

    Returns
    -------
    FieldValidation
        Resultado de la validación.
    """
    if field_name not in data:
        return FieldValidation(
            field_name=field_name,
            exists=False,
            expected_type=str(expected_type),
            actual_type="N/A",
            is_valid=not required,
            message="Campo ausente" if required else "Campo opcional ausente",
        )

    value = data[field_name]
    actual_type = type(value).__name__

    if isinstance(expected_type, tuple):
        is_correct_type = isinstance(value, expected_type)
        expected_str = " | ".join(t.__name__ for t in expected_type)
    else:
        is_correct_type = isinstance(value, expected_type)
        expected_str = expected_type.__name__

    if not is_correct_type:
        return FieldValidation(
            field_name=field_name,
            exists=True,
            expected_type=expected_str,
            actual_type=actual_type,
            is_valid=False,
            message=f"Tipo incorrecto: esperado {expected_str}, obtenido {actual_type}",
        )

    # Verificar valores vacíos
    if value is None:
        return FieldValidation(
            field_name=field_name,
            exists=True,
            expected_type=expected_str,
            actual_type=actual_type,
            is_valid=not required,
            message="Valor nulo",
        )

    if isinstance(value, (str, list, dict)) and len(value) == 0:
        return FieldValidation(
            field_name=field_name,
            exists=True,
            expected_type=expected_str,
            actual_type=actual_type,
            is_valid=True,  # Vacío pero válido estructuralmente
            message="Colección o cadena vacía",
        )

    return FieldValidation(
        field_name=field_name,
        exists=True,
        expected_type=expected_str,
        actual_type=actual_type,
        is_valid=True,
        message="OK",
    )


def evaluate_gdc_json(file_path: Path) -> QualityReport:
    """
    Evalúa la calidad de un fichero JSON de GDC.

    Parameters
    ----------
    file_path : Path
        Ruta al fichero JSON de GDC.

    Returns
    -------
    QualityReport
        Reporte de calidad del fichero.
    """
    report = QualityReport(source="GDC", file_path=str(file_path))

    if not file_path.exists():
        report.add_error(f"Fichero no encontrado: {file_path}")
        return report

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        report.add_error(f"Error de parsing JSON: {e}")
        return report
    except Exception as e:
        report.add_error(f"Error al leer fichero: {e}")
        return report

    # El fichero GDC puede ser una lista de proyectos o un documento único
    if isinstance(data, list):
        projects = data
        report.document_count = len(projects)
    elif isinstance(data, dict):
        projects = [data]
        report.document_count = 1
    else:
        report.add_error(f"Formato inesperado: esperado dict o list, obtenido {type(data).__name__}")
        return report

    total_cases = 0
    total_files = 0

    for project in projects:
        # Validar campos requeridos del proyecto
        for field_name, field_type in GDC_SCHEMA["required_fields"].items():
            validation = validate_field(project, field_name, field_type)
            report.field_validations.append(validation)
            report.stats.total_fields += 1
            if validation.is_valid:
                report.stats.valid_fields += 1
            elif not validation.exists:
                report.stats.missing_fields += 1
            else:
                report.stats.invalid_type_fields += 1

        # Validar casos
        cases = project.get("cases", [])
        if not cases:
            report.add_warning(f"Proyecto {project.get('project_id', 'UNKNOWN')}: sin casos")
            report.stats.empty_collections += 1

        for case in cases:
            total_cases += 1
            for field_name, field_type in GDC_SCHEMA["case_fields"].items():
                validation = validate_field(case, field_name, field_type)
                report.stats.total_fields += 1
                if validation.is_valid:
                    report.stats.valid_fields += 1
                elif not validation.exists:
                    report.stats.missing_fields += 1

            # Validar ficheros
            files = case.get("files", [])
            for file_doc in files:
                total_files += 1
                for field_name, field_type in GDC_SCHEMA["file_fields"].items():
                    validation = validate_field(file_doc, field_name, field_type)
                    report.stats.total_fields += 1
                    if validation.is_valid:
                        report.stats.valid_fields += 1
                    elif not validation.exists:
                        report.stats.missing_fields += 1

    logger.info(f"[GDC] Proyectos: {report.document_count}, Casos: {total_cases}, Ficheros: {total_files}")
    report.calculate_completeness()
    return report


def evaluate_hgnc_json(file_path: Path) -> QualityReport:
    """
    Evalúa la calidad de un fichero JSON de HGNC.

    Parameters
    ----------
    file_path : Path
        Ruta al fichero JSON de HGNC.

    Returns
    -------
    QualityReport
        Reporte de calidad del fichero.
    """
    report = QualityReport(source="HGNC", file_path=str(file_path))

    if not file_path.exists():
        report.add_error(f"Fichero no encontrado: {file_path}")
        return report

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        report.add_error(f"Error de parsing JSON: {e}")
        return report
    except Exception as e:
        report.add_error(f"Error al leer fichero: {e}")
        return report

    # El fichero HGNC es normalmente una lista de genes
    if isinstance(data, list):
        genes = data
        report.document_count = len(genes)
    elif isinstance(data, dict):
        # Puede ser un documento con campo "genes" o similar
        if "genes" in data:
            genes = data["genes"]
        elif "hgnc_genes" in data:
            genes = data["hgnc_genes"]
        else:
            genes = [data]
        report.document_count = len(genes)
    else:
        report.add_error(f"Formato inesperado: esperado dict o list, obtenido {type(data).__name__}")
        return report

    genes_with_ensembl = 0
    genes_with_uniprot = 0
    genes_with_projects = 0

    for gene in genes:
        if not isinstance(gene, dict):
            report.add_warning(f"Elemento no es dict: {type(gene).__name__}")
            continue

        # Validar campos requeridos
        for field_name, field_type in HGNC_SCHEMA["required_fields"].items():
            validation = validate_field(gene, field_name, field_type)
            report.stats.total_fields += 1
            if validation.is_valid:
                report.stats.valid_fields += 1
            elif not validation.exists:
                report.stats.missing_fields += 1
            else:
                report.stats.invalid_type_fields += 1

        # Validar campos opcionales
        for field_name, field_type in HGNC_SCHEMA["optional_fields"].items():
            validation = validate_field(gene, field_name, field_type, required=False)
            report.stats.total_fields += 1
            if validation.is_valid:
                report.stats.valid_fields += 1

        # Estadísticas adicionales
        if gene.get("ensembl_gene_id"):
            genes_with_ensembl += 1
        if gene.get("uniprot_ids"):
            genes_with_uniprot += 1
        if gene.get("projects") and len(gene.get("projects", {})) > 0:
            genes_with_projects += 1

    logger.info(f"[HGNC] Total genes: {report.document_count}")
    logger.info(f"[HGNC] Genes con Ensembl ID: {genes_with_ensembl} ({genes_with_ensembl/max(1,report.document_count)*100:.1f}%)")
    logger.info(f"[HGNC] Genes con UniProt ID: {genes_with_uniprot} ({genes_with_uniprot/max(1,report.document_count)*100:.1f}%)")
    logger.info(f"[HGNC] Genes con proyectos: {genes_with_projects} ({genes_with_projects/max(1,report.document_count)*100:.1f}%)")

    report.calculate_completeness()
    return report


def evaluate_uniprot_json(file_path: Path) -> QualityReport:
    """
    Evalúa la calidad de un fichero JSON de UniProt.

    Parameters
    ----------
    file_path : Path
        Ruta al fichero JSON de UniProt.

    Returns
    -------
    QualityReport
        Reporte de calidad del fichero.
    """
    report = QualityReport(source="UniProt", file_path=str(file_path))

    if not file_path.exists():
        report.add_error(f"Fichero no encontrado: {file_path}")
        return report

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        report.add_error(f"Error de parsing JSON: {e}")
        return report
    except Exception as e:
        report.add_error(f"Error al leer fichero: {e}")
        return report

    # Validar estructura principal
    if isinstance(data, dict):
        # Formato esperado: {"uniprot_entries": [...]}
        for field_name, field_type in UNIPROT_SCHEMA["required_fields"].items():
            validation = validate_field(data, field_name, field_type)
            report.field_validations.append(validation)
            report.stats.total_fields += 1
            if validation.is_valid:
                report.stats.valid_fields += 1
            elif not validation.exists:
                report.stats.missing_fields += 1

        entries = data.get("uniprot_entries", [])
    elif isinstance(data, list):
        # Formato alternativo: lista directa de entries
        entries = data
    else:
        report.add_error(f"Formato inesperado: esperado dict o list, obtenido {type(data).__name__}")
        return report

    report.document_count = len(entries)
    entries_with_gene = 0
    entries_with_projects = 0

    for entry in entries:
        if not isinstance(entry, dict):
            report.add_warning(f"Entry no es dict: {type(entry).__name__}")
            continue

        # Validar campos de entry
        for field_name, field_type in UNIPROT_SCHEMA["entry_fields"].items():
            validation = validate_field(entry, field_name, field_type)
            report.stats.total_fields += 1
            if validation.is_valid:
                report.stats.valid_fields += 1
            elif not validation.exists:
                report.stats.missing_fields += 1

        # Validar campos opcionales
        for field_name, field_type in UNIPROT_SCHEMA["optional_entry_fields"].items():
            validation = validate_field(entry, field_name, field_type, required=False)
            report.stats.total_fields += 1
            if validation.is_valid:
                report.stats.valid_fields += 1

        # Estadísticas adicionales
        if entry.get("gene_primary") or entry.get("gene"):
            entries_with_gene += 1
        if entry.get("projects") and len(entry.get("projects", {})) > 0:
            entries_with_projects += 1

    logger.info(f"[UniProt] Total entries: {report.document_count}")
    logger.info(f"[UniProt] Entries con gen: {entries_with_gene} ({entries_with_gene/max(1,report.document_count)*100:.1f}%)")
    logger.info(f"[UniProt] Entries con proyectos: {entries_with_projects} ({entries_with_projects/max(1,report.document_count)*100:.1f}%)")

    report.calculate_completeness()
    return report


def evaluate_all_json(
    gdc_path: Optional[Path] = None,
    hgnc_path: Optional[Path] = None,
    uniprot_path: Optional[Path] = None,
) -> dict[str, QualityReport]:
    """
    Evalúa todos los ficheros JSON especificados.

    Parameters
    ----------
    gdc_path : Path, optional
        Ruta al JSON de GDC.
    hgnc_path : Path, optional
        Ruta al JSON de HGNC.
    uniprot_path : Path, optional
        Ruta al JSON de UniProt.

    Returns
    -------
    dict[str, QualityReport]
        Diccionario con reportes por fuente.
    """
    reports = {}

    if gdc_path:
        logger.info(f"Evaluando GDC: {gdc_path}")
        reports["GDC"] = evaluate_gdc_json(Path(gdc_path))

    if hgnc_path:
        logger.info(f"Evaluando HGNC: {hgnc_path}")
        reports["HGNC"] = evaluate_hgnc_json(Path(hgnc_path))

    if uniprot_path:
        logger.info(f"Evaluando UniProt: {uniprot_path}")
        reports["UniProt"] = evaluate_uniprot_json(Path(uniprot_path))

    return reports


def print_quality_report(report: QualityReport) -> None:
    """
    Imprime un reporte de calidad de forma legible.

    Parameters
    ----------
    report : QualityReport
        Reporte a imprimir.
    """
    print(f"\n{'='*80}")
    print(f"REPORTE DE CALIDAD - {report.source}")
    print(f"{'='*80}")
    print(f"  Fichero:            {report.file_path}")
    print(f"  Estado:             {'VÁLIDO' if report.is_valid else 'INVÁLIDO'}")
    print(f"  Documentos:         {report.document_count}")
    print(f"  Completitud:        {report.completeness_score:.1f}%")
    print()
    print("  Estadísticas de campos:")
    print(f"    - Total campos:       {report.stats.total_fields}")
    print(f"    - Campos válidos:     {report.stats.valid_fields}")
    print(f"    - Campos ausentes:    {report.stats.missing_fields}")
    print(f"    - Tipo incorrecto:    {report.stats.invalid_type_fields}")
    print(f"    - Valores nulos:      {report.stats.null_fields}")
    print(f"    - Colecciones vacías: {report.stats.empty_collections}")

    if report.errors:
        print()
        print(f"  Errores ({len(report.errors)}):")
        for error in report.errors:
            print(f"    - {error}")

    if report.warnings:
        print()
        print(f"  Warnings ({len(report.warnings)}):")
        for warning in report.warnings[:10]:  # Limitar a 10 warnings
            print(f"    - {warning}")
        if len(report.warnings) > 10:
            print(f"    ... y {len(report.warnings) - 10} más")

    print(f"{'='*80}")


def run_quality_evaluation(
    gdc_json_path: Optional[str] = None,
    hgnc_json_path: Optional[str] = None,
    uniprot_json_path: Optional[str] = None,
    verbose: bool = True,
) -> dict[str, QualityReport]:
    """
    Ejecuta la evaluación de calidad completa.

    Esta es la función principal para ejecutar la evaluación de calidad
    desde el pipeline.

    Parameters
    ----------
    gdc_json_path : str, optional
        Ruta al JSON de GDC.
    hgnc_json_path : str, optional
        Ruta al JSON de HGNC.
    uniprot_json_path : str, optional
        Ruta al JSON de UniProt.
    verbose : bool
        Si True, imprime los reportes.

    Returns
    -------
    dict[str, QualityReport]
        Diccionario con reportes por fuente.
    """
    logger.info("=" * 80)
    logger.info("INICIANDO EVALUACIÓN DE CALIDAD")
    logger.info("=" * 80)

    reports = evaluate_all_json(
        gdc_path=Path(gdc_json_path) if gdc_json_path else None,
        hgnc_path=Path(hgnc_json_path) if hgnc_json_path else None,
        uniprot_path=Path(uniprot_json_path) if uniprot_json_path else None,
    )

    if verbose:
        for source, report in reports.items():
            print_quality_report(report)

    # Resumen final
    all_valid = all(r.is_valid for r in reports.values())
    avg_completeness = sum(r.completeness_score for r in reports.values()) / max(1, len(reports))
    total_errors = sum(len(r.errors) for r in reports.values())
    total_warnings = sum(len(r.warnings) for r in reports.values())

    print()
    print("=" * 80)
    print("RESUMEN DE EVALUACIÓN DE CALIDAD")
    print("=" * 80)
    print(f"  Fuentes evaluadas:   {len(reports)}")
    print(f"  Estado global:       {'TODOS VÁLIDOS' if all_valid else 'HAY ERRORES'}")
    print(f"  Completitud media:   {avg_completeness:.1f}%")
    print(f"  Total errores:       {total_errors}")
    print(f"  Total warnings:      {total_warnings}")
    print("=" * 80)

    logger.info("Evaluación de calidad completada")
    return reports
