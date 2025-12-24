```bash
# Execute from project root: /home/mpascual/research/code/ProyectoEstandaresDatos

# Step 1: Execute Query6 to generate ontology individual JSON
biointegrate-execute-queries \
    --config config/queries/mario_queries.yaml \
    --queries docs/t2-queries/Query6_OntologyIndividual.txt \
    --output-dir docs/t2-resultados

# Step 2: Populate the reasoned ontology with the query results
biointegrate-populate-ontology \
    --input docs/t2-resultados/query_6_ontology_individual.json \
    --ontology ontology/assets/biointegrate-ontology-reasoned.owl \
    --output ontology/assets/biointegrate_populated.owl
```

To accumulate more individuals (run Query6 multiple times for different genes):

```bash
# Subsequent runs: use populated ontology as both input and output
biointegrate-execute-queries \
    --config config/queries/mario_queries.yaml \
    --queries docs/t2-queries/Query6_OntologyIndividual.txt \
    --output-dir docs/t2-resultados

biointegrate-populate-ontology \
    --input docs/t2-resultados/query_6_ontology_individual.json \
    --ontology ontology/data/owl/biointegrate-ontology-reasoned.owl \
    --output ontology/data/owl/biointegrate-ontology-reasoned.owl
```
