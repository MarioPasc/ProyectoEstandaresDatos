# Ejemplo de uso

```bash
(datastandards) mpascual@mpascual:~/research/code/ProyectoEstandaresDatos$ biointegrate-execute-queries --config config/queries/mario_queries.yaml --queries docs/t2-queries-ejemplos/queries/query_smoke_test_1.txt,docs/t2-queries-ejemplos/queries/query_smoke_test_2.txt --dry-run 
2025-11-25 20:36:22,901 - biointegrate.cli.queries - INFO - Target database: estandares_db
2025-11-25 20:36:22,901 - biointegrate.cli.queries - INFO - Parsing query file paths: docs/t2-queries-ejemplos/queries/query_smoke_test_1.txt,docs/t2-queries-ejemplos/queries/query_smoke_test_2.txt
2025-11-25 20:36:22,901 - biointegrate.cli.queries - INFO - Found 2 query files
2025-11-25 20:36:22,901 - biointegrate.cli.queries - INFO - Loading query specifications...
2025-11-25 20:36:22,901 - biointegrate.cli.queries - INFO - Loaded 2 valid queries
2025-11-25 20:36:22,901 - biointegrate.cli.queries - INFO - DRY RUN MODE: Configuration and queries validated successfully

✓ Dry run completed successfully
  Config: config/queries/mario_queries.yaml
  Queries: 2 validated
(datastandards) mpascual@mpascual:~/research/code/ProyectoEstandaresDatos$ biointegrate-execute-queries --config config/queries/mario_queries.yaml --queries docs/t2-queries-ejemplos/queries/query_smoke_test_1.txt,docs/t2-queries-ejemplos/queries/query_smoke_test_2.txt 
2025-11-25 20:36:28,930 - biointegrate.cli.queries - INFO - Target database: estandares_db
2025-11-25 20:36:28,930 - biointegrate.cli.queries - INFO - Parsing query file paths: docs/t2-queries-ejemplos/queries/query_smoke_test_1.txt,docs/t2-queries-ejemplos/queries/query_smoke_test_2.txt
2025-11-25 20:36:28,930 - biointegrate.cli.queries - INFO - Found 2 query files
2025-11-25 20:36:28,930 - biointegrate.cli.queries - INFO - Loading query specifications...
2025-11-25 20:36:28,930 - biointegrate.cli.queries - INFO - Loaded 2 valid queries
2025-11-25 20:36:28,930 - biointegrate.cli.queries - INFO - Executing queries against MongoDB...
2025-11-25 20:36:28,933 - biointegrate.queries.mongo_executor - INFO - Connected to MongoDB: estandares_db
2025-11-25 20:36:28,933 - biointegrate.queries.mongo_executor - INFO - Executing query 'hgnc_find_tp53' (type=find, collection=hgnc_genes)
2025-11-25 20:36:28,947 - biointegrate.queries.mongo_executor - INFO - Query 'hgnc_find_tp53' on 'hgnc_genes': 1 documents returned
2025-11-25 20:36:28,947 - biointegrate.queries.mongo_executor - INFO - Executing query 'hgnc_count_by_chromosome' (type=aggregate, collection=hgnc_genes)
2025-11-25 20:36:28,969 - biointegrate.queries.mongo_executor - INFO - Query 'hgnc_count_by_chromosome' on 'hgnc_genes': 1 documents returned

============================================================
QUERY EXECUTION SUMMARY
============================================================
  hgnc_find_tp53: 1 documents
  hgnc_count_by_chromosome: 1 documents
============================================================

2025-11-25 20:36:28,970 - biointegrate.cli.queries - INFO - ✓ All queries executed successfully
```