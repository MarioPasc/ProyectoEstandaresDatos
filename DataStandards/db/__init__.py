"""
DataStandards.db

Módulo de importadores de datos a MongoDB.

Issue: T1 - Importadores MongoDB para genes, proteínas y GDC
"""

from . import import_proteins_mongo
from .import_genes_mongo import import_genes_mongo
from .import_proteins_mongo import import_proteins_mongo
from .import_gdc_mongo import import_gdc_mongo
from .gdc_config import gdc_config
__all__ = [
    'import_genes_mongo',
    'import_proteins_mongo',
    'import_gdc_mongo',
    'gdc_config'
]
