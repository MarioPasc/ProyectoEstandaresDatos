"""
presentation.py

Módulo de presentación para el pipeline de Estándares de Datos.
Muestra información del proyecto, autores, configuración y solicita confirmación del usuario.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


# Banner ASCII personalizado para el proyecto
BANNER = r"""
╔═══════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                                                                                   ║
║   ██████╗ ██╗ ██████╗ ██╗███╗   ██╗████████╗███████╗ ██████╗ ██████╗  █████╗ ████████╗███████╗    ║
║   ██╔══██╗██║██╔═══██╗██║████╗  ██║╚══██╔══╝██╔════╝██╔════╝ ██╔══██╗██╔══██╗╚══██╔══╝██╔════╝    ║
║   ██████╔╝██║██║   ██║██║██╔██╗ ██║   ██║   █████╗  ██║  ███╗██████╔╝███████║   ██║   █████╗      ║
║   ██╔══██╗██║██║   ██║██║██║╚██╗██║   ██║   ██╔══╝  ██║   ██║██╔══██╗██╔══██║   ██║   ██╔══╝      ║
║   ██████╔╝██║╚██████╔╝██║██║ ╚████║   ██║   ███████╗╚██████╔╝██║  ██║██║  ██║   ██║   ███████╗    ║ 
║   ╚═════╝ ╚═╝ ╚═════╝ ╚═╝╚═╝  ╚═══╝   ╚═╝   ╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   ╚══════╝    ║
║                                                                                                   ║
║                                                                                                   ║
║                         Pipeline de Integración de Datos Bioinformáticos                          ║
║                            GDC · HGNC · UniProt → MongoDB / JSON                                  ║
║                                                                                                   ║
╚═══════════════════════════════════════════════════════════════════════════════════════════════════╝
"""

# Información del proyecto
PROJECT_INFO = {
    "name": "BioIntegrate - Pipeline de Integración de Datos Bioinformáticos",
    "version": "0.1.0",
    "course": "Estándares de Datos",
    "university": "Universidad de Málaga (UMA)",
    "academic_year": "2024-2025",
    "tutor": "Dr.Rybinski, Maciej",
    "repository": "https://github.com/MarioPasc/ProyectoEstandaresDatos",
}

# Lista de autores del proyecto
AUTHORS = [
    {"name": "Mario Pascual-González", "email": "mpascual@uma.es", "role": "Lead Developer"},
    {"name": "Teresa Vega Martínez", "email": "teresavegamar@gmail.com", "role": "Developer"},
    {"name": "Juan Soriano", "email": "0610948742@uma.es", "role": "Developer"},
    {"name": "Ainhoa Pérez", "email": "ainhoa140602@gmail.com", "role": "Developer"},
    {"name": "Martina Cebolla Salas", "email": "martinacesalas@gmail.com", "role": "Developer"},
]


def print_separator(char: str = "═", length: int = 100) -> None:
    """Imprime una línea separadora."""
    print(char * length)


def print_section_header(title: str, char: str = "─", length: int = 100) -> None:
    """Imprime un encabezado de sección."""
    padding = (length - len(title) - 4) // 2
    print(f"\n{char * padding} {title} {char * padding}")


def format_datetime() -> tuple[str, str]:
    """Retorna la fecha y hora actuales formateadas."""
    now = datetime.now()
    date_str = now.strftime("%d de %B de %Y")
    time_str = now.strftime("%H:%M:%S")

    # Traducir meses al español
    months_es = {
        "January": "enero", "February": "febrero", "March": "marzo",
        "April": "abril", "May": "mayo", "June": "junio",
        "July": "julio", "August": "agosto", "September": "septiembre",
        "October": "octubre", "November": "noviembre", "December": "diciembre"
    }
    for en, es in months_es.items():
        date_str = date_str.replace(en, es)

    return date_str, time_str


def print_banner() -> None:
    """Imprime el banner del proyecto."""
    print(BANNER)


def print_project_info() -> None:
    """Imprime la información general del proyecto."""
    print_section_header("INFORMACIÓN DEL PROYECTO")
    print(f"  Proyecto:       {PROJECT_INFO['name']}")
    print(f"  Versión:        {PROJECT_INFO['version']}")
    print(f"  Asignatura:     {PROJECT_INFO['course']}")
    print(f"  Universidad:    {PROJECT_INFO['university']}")
    print(f"  Curso académico: {PROJECT_INFO['academic_year']}")
    print(f"  Repositorio:    {PROJECT_INFO['repository']}")


def print_tutor_info() -> None:
    """Imprime la información del tutor."""
    print_section_header("TUTOR ASIGNADO")
    print(f"  Nombre:         {PROJECT_INFO['tutor']}")
    print(f"  Universidad:    {PROJECT_INFO['university']}")


def print_authors() -> None:
    """Imprime la lista de autores del proyecto."""
    print_section_header("EQUIPO DE DESARROLLO")
    for i, author in enumerate(AUTHORS, 1):
        print(f"  {i}. {author['name']}")
        print(f"     Email: {author['email']}")
        print(f"     Rol:   {author['role']}")
        if i < len(AUTHORS):
            print()


def print_datetime_info() -> None:
    """Imprime la fecha y hora de ejecución."""
    date_str, time_str = format_datetime()
    print_section_header("FECHA Y HORA DE EJECUCIÓN")
    print(f"  Fecha:          {date_str}")
    print(f"  Hora:           {time_str}")


def print_config_summary(
    data_config_path: Path,
    mongo_config_path: Path,
    data_config: Any,
    mongo_config: Any,
    no_insert: bool = False,
    skip_download: bool = False,
    skip_quality: bool = False,
) -> None:
    """
    Imprime un resumen de la configuración proporcionada.

    Parameters
    ----------
    data_config_path : Path
        Ruta al fichero de configuración de datos.
    mongo_config_path : Path
        Ruta al fichero de configuración de MongoDB.
    data_config : Any
        Objeto de configuración de datos cargado.
    mongo_config : Any
        Objeto de configuración de MongoDB cargado.
    no_insert : bool
        Si True, no se insertarán datos en MongoDB.
    skip_download : bool
        Si True, se omitirá la descarga de datos.
    skip_quality : bool
        Si True, se omitirá la evaluación de calidad.
    """
    print_section_header("CONFIGURACIÓN DEL PIPELINE")

    # Rutas de configuración
    print("\n  Ficheros de configuración:")
    print(f"    - Datos:    {data_config_path}")
    print(f"    - MongoDB:  {mongo_config_path}")

    # Opciones del pipeline
    print("\n  Opciones del pipeline:")
    print(f"    - Descargar datos:       {'Sí' if not skip_download else 'No (omitido)'}")
    print(f"    - Crear JSONs:           Sí")
    print(f"    - Insertar en MongoDB:   {'No (--no-insert)' if no_insert else 'Sí'}")
    print(f"    - Evaluación de calidad: {'No (omitido)' if skip_quality else 'Sí'}")

    # Configuración GDC
    if hasattr(data_config, 'gdc') and data_config.gdc:
        gdc = data_config.gdc
        print("\n  Configuración GDC:")
        print(f"    - URL base:        {gdc.base_url}")
        if hasattr(gdc, 'project_ids'):
            print(f"    - Proyectos:       {', '.join(gdc.project_ids)}")
        if hasattr(gdc, 'base_output_dir'):
            print(f"    - Directorio:      {gdc.base_output_dir}")
        if hasattr(gdc, 'rnaseq') and gdc.rnaseq:
            print(f"    - Max ficheros:    {gdc.rnaseq.max_files}")

    # Configuración HGNC
    if hasattr(data_config, 'hgnc') and data_config.hgnc:
        hgnc = data_config.hgnc
        print("\n  Configuración HGNC:")
        print(f"    - Destino:         {hgnc.output_path}")

    # Configuración UniProt
    if hasattr(data_config, 'uniprot') and data_config.uniprot:
        uniprot = data_config.uniprot
        print("\n  Configuración UniProt:")
        print(f"    - Habilitado:      {'Sí' if uniprot.enabled else 'No'}")
        if hasattr(uniprot, 'base_output_dir'):
            print(f"    - Directorio:      {uniprot.base_output_dir}")
        if hasattr(uniprot, 'max_accessions'):
            print(f"    - Max accessions:  {uniprot.max_accessions}")

    # Configuración MongoDB
    if hasattr(mongo_config, 'mongodb') and mongo_config.mongodb:
        mongo = mongo_config.mongodb
        print("\n  Configuración MongoDB:")
        print(f"    - URI:             {mongo.mongo_uri}")
        print(f"    - Base de datos:   {mongo.database_name}")
        if hasattr(mongo, 'collection_name'):
            print(f"    - Colección GDC:   {mongo.collection_name}")
        if hasattr(mongo, 'hgnc_collection_name'):
            print(f"    - Colección HGNC:  {mongo.hgnc_collection_name}")

    # Rutas de salida JSON
    if hasattr(mongo_config, 'options') and mongo_config.options:
        opts = mongo_config.options
        print("\n  Salidas JSON:")
        if hasattr(opts, 'save_as_json_gdc') and opts.save_as_json_gdc:
            print(f"    - GDC:             {opts.save_as_json_gdc}")
        if hasattr(opts, 'save_as_json_hgnc') and opts.save_as_json_hgnc:
            print(f"    - HGNC:            {opts.save_as_json_hgnc}")
        if hasattr(opts, 'save_as_json_uniprot') and opts.save_as_json_uniprot:
            print(f"    - UniProt:         {opts.save_as_json_uniprot}")


def print_pipeline_steps(
    skip_download: bool = False,
    no_insert: bool = False,
    skip_quality: bool = False,
) -> None:
    """Imprime los pasos que se ejecutarán en el pipeline."""
    print_section_header("PASOS DEL PIPELINE")

    step = 1

    if not skip_download:
        print(f"\n  Paso {step}: DESCARGA DE DATOS")
        print("    - Descargar manifests y metadatos de GDC")
        print("    - Descargar ficheros RNA-seq STAR-Counts")
        print("    - Descargar conjunto completo HGNC")
        print("    - Consultar API de UniProt")
        step += 1

    print(f"\n  Paso {step}: CREACIÓN DE BASE DE DATOS JSON")
    print("    - Procesar datos GDC y crear documento JSON")
    print("    - Integrar datos HGNC con expresión génica")
    print("    - Crear documentos UniProt con mapeos")
    if not no_insert:
        print("    - Insertar documentos en colecciones MongoDB")
    else:
        print("    - (Solo generación de JSON, sin inserción en MongoDB)")
    step += 1

    if not skip_quality:
        print(f"\n  Paso {step}: EVALUACIÓN DE CALIDAD")
        print("    - Verificar estructura de documentos JSON")
        print("    - Validar campos requeridos")
        print("    - Calcular estadísticas de completitud")
        print("    - Generar reporte de calidad")


def request_user_confirmation() -> bool:
    """
    Solicita confirmación del usuario para continuar con el pipeline.

    Returns
    -------
    bool
        True si el usuario confirma (y), False si cancela (n).
    """
    print_separator("═")
    print("\n¿Desea continuar con la ejecución del pipeline?")
    print("  Escriba 'y' para continuar o 'n' para cancelar.")
    print()

    while True:
        try:
            response = input("  >>> ").strip().lower()
            if response == 'y':
                print("\n  Iniciando pipeline...\n")
                return True
            elif response == 'n':
                print("\n  Pipeline cancelado por el usuario.\n")
                return False
            else:
                print("  Por favor, escriba 'y' para continuar o 'n' para cancelar.")
        except (KeyboardInterrupt, EOFError):
            print("\n\n  Pipeline cancelado por el usuario.\n")
            return False


def show_presentation(
    data_config_path: Path,
    mongo_config_path: Path,
    data_config: Any,
    mongo_config: Any,
    no_insert: bool = False,
    skip_download: bool = False,
    skip_quality: bool = False,
) -> bool:
    """
    Muestra la presentación completa del proyecto y solicita confirmación.

    Esta función es el punto de entrada principal del módulo de presentación.
    Muestra el banner, información del proyecto, autores, tutor, fecha/hora,
    configuración y los pasos del pipeline, y luego solicita confirmación.

    Parameters
    ----------
    data_config_path : Path
        Ruta al fichero de configuración de datos.
    mongo_config_path : Path
        Ruta al fichero de configuración de MongoDB.
    data_config : Any
        Objeto de configuración de datos cargado.
    mongo_config : Any
        Objeto de configuración de MongoDB cargado.
    no_insert : bool
        Si True, no se insertarán datos en MongoDB.
    skip_download : bool
        Si True, se omitirá la descarga de datos.
    skip_quality : bool
        Si True, se omitirá la evaluación de calidad.

    Returns
    -------
    bool
        True si el usuario confirma la ejecución, False si cancela.
    """
    # Limpiar pantalla (opcional, comentado por defecto)
    # print("\033[2J\033[H", end="")

    # Mostrar banner
    print_banner()

    # Mostrar información del proyecto
    print_project_info()

    # Mostrar tutor
    print_tutor_info()

    # Mostrar autores
    print_authors()

    # Mostrar fecha y hora
    print_datetime_info()

    # Mostrar configuración
    print_config_summary(
        data_config_path=data_config_path,
        mongo_config_path=mongo_config_path,
        data_config=data_config,
        mongo_config=mongo_config,
        no_insert=no_insert,
        skip_download=skip_download,
        skip_quality=skip_quality,
    )

    # Mostrar pasos del pipeline
    print_pipeline_steps(
        skip_download=skip_download,
        no_insert=no_insert,
        skip_quality=skip_quality,
    )

    # Solicitar confirmación
    return request_user_confirmation()
