"""
Módulo de ejecución de consultas MongoDB desde especificaciones externas.

Este módulo proporciona funcionalidad para:
- Cargar y validar configuración de conexión desde YAML
- Parsear especificaciones de consultas desde ficheros JSON/TXT
- Ejecutar consultas find y aggregate contra MongoDB
- Guardar resultados en formato JSON
"""

from biointegrate.queries.query_parser import (
    MongoQuery,
    QuerySpecError,
    QueryFileNotFoundError,
    parse_queries_arg,
    parse_query_spec,
    load_queries,
)

from biointegrate.queries.mongo_executor import (
    MongoConnectionError,
    QueryExecutionError,
    run_mongo_query,
    run_mongo_queries,
)

__all__ = [
    # Query parsing
    "MongoQuery",
    "QuerySpecError",
    "QueryFileNotFoundError",
    "parse_queries_arg",
    "parse_query_spec",
    "load_queries",
    # MongoDB execution
    "MongoConnectionError",
    "QueryExecutionError",
    "run_mongo_query",
    "run_mongo_queries",
]
