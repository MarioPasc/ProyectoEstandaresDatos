```bash
# First run: start from base ontology
biointegrate-populate-ontology \
    --input result1.json \
    --ontology ontology/assets/biointegrate.owl \
    --output ontology/assets/biointegrate_populated.owl

# Second run: use the populated ontology as input AND output
biointegrate-populate-ontology \
    --input result2.json \
    --ontology ontology/assets/biointegrate_populated.owl \
    --output ontology/assets/biointegrate_populated.owl

# Third run: keeps accumulating
biointegrate-populate-ontology \
    --input result3.json \
    --ontology ontology/assets/biointegrate_populated.owl \
    --output ontology/assets/biointegrate_populated.owl
```
