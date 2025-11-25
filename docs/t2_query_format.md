# T2 Query File Format

Query specification format for `biointegrate-execute-queries`.

## Format: JSON (in .txt or .json files)

Query specifications are written in JSON format and can be stored in `.txt` or `.json` files.

## Required Fields

All query files must include:

- `name` (string): Unique identifier for this query
  - Used in logging and output filenames
  - Example: `"hgnc_find_tp53"`

- `collection` (string): MongoDB collection name
  - Example: `"hgnc_genes"`, `"uniprot_entries"`

- `type` (string): Query type
  - Valid values: `"find"` or `"aggregate"`

## Type-Specific Fields

### For `type: "find"`

**Required:**
- `filter` (object): MongoDB query filter
  - Example: `{"symbol": "TP53"}`
  - Example: `{"symbol": {"$in": ["TP53", "BRCA1"]}}`

**Optional:**
- `projection` (object): Field projection
  - Example: `{"_id": 0, "symbol": 1, "hgnc_id": 1}`
  - Use `1` to include fields, `0` to exclude fields

### For `type: "aggregate"`

**Required:**
- `pipeline` (array): Aggregation pipeline stages
  - Must be non-empty array
  - Each element is a pipeline stage (e.g., `$match`, `$group`, `$lookup`)
  - Example: `[{"$match": {...}}, {"$group": {...}}]`

## Examples

### Example 1: Simple Find Query

Find a specific gene by symbol:

```json
{
  "name": "find_gene_tp53",
  "collection": "hgnc_genes",
  "type": "find",
  "filter": {
    "symbol": "TP53"
  },
  "projection": {
    "_id": 0,
    "symbol": 1,
    "hgnc_id": 1,
    "ensembl_gene_id": 1
  }
}
```

### Example 2: Find with Complex Filter

Find multiple genes using `$in` operator:

```json
{
  "name": "find_cancer_genes",
  "collection": "hgnc_genes",
  "type": "find",
  "filter": {
    "symbol": {"$in": ["TP53", "BRCA1", "BRCA2", "EGFR"]}
  },
  "projection": {
    "_id": 0,
    "symbol": 1,
    "hgnc_id": 1
  }
}
```

### Example 3: Aggregate with Grouping

Count genes by chromosome location:

```json
{
  "name": "count_genes_by_location",
  "collection": "hgnc_genes",
  "type": "aggregate",
  "pipeline": [
    {
      "$group": {
        "_id": "$location",
        "total": {"$sum": 1}
      }
    },
    {
      "$sort": {"total": -1}
    },
    {
      "$limit": 10
    }
  ]
}
```

### Example 4: Join with $lookup

Join HGNC genes with UniProt proteins:

```json
{
  "name": "hgnc_uniprot_join",
  "collection": "hgnc_genes",
  "type": "aggregate",
  "pipeline": [
    {
      "$match": {"symbol": "BRCA1"}
    },
    {
      "$unwind": "$uniprot_ids"
    },
    {
      "$lookup": {
        "from": "uniprot_entries",
        "localField": "uniprot_ids",
        "foreignField": "uniprot_id",
        "as": "protein_data"
      }
    },
    {
      "$project": {
        "_id": 0,
        "gene_symbol": "$symbol",
        "hgnc_id": 1,
        "uniprot_id": "$uniprot_ids",
        "protein_name": {"$arrayElemAt": ["$protein_data.protein.names", 0]}
      }
    }
  ]
}
```

## How Joins Work with $lookup

The `$lookup` stage performs a left outer join between collections:

```json
{
  "$lookup": {
    "from": "target_collection",
    "localField": "field_in_source",
    "foreignField": "field_in_target",
    "as": "output_array_name"
  }
}
```

**Example**: Join HGNC genes with UniProt proteins

- Source collection: `hgnc_genes`
- Target collection: `uniprot_entries`
- Join condition: `hgnc.uniprot_ids = uniprot.uniprot_id`

```
hgnc_genes.uniprot_ids → uniprot_entries.uniprot_id
```

## Common Aggregation Operators

| Operator | Purpose | Example |
|----------|---------|---------|
| `$match` | Filter documents | `{"$match": {"symbol": "TP53"}}` |
| `$group` | Group by field | `{"$group": {"_id": "$location", "count": {"$sum": 1}}}` |
| `$sort` | Sort results | `{"$sort": {"count": -1}}` |
| `$limit` | Limit results | `{"$limit": 10}` |
| `$project` | Select/reshape fields | `{"$project": {"_id": 0, "symbol": 1}}` |
| `$unwind` | Deconstruct array | `{"$unwind": "$uniprot_ids"}` |
| `$lookup` | Join collections | See example above |

## Invalid Examples

**Missing required field:**
```json
{
  "collection": "hgnc_genes",
  "type": "find",
  "filter": {}
}
// ERROR: Missing 'name'
```

**Wrong type-specific field:**
```json
{
  "name": "bad_query",
  "collection": "test",
  "type": "find",
  "pipeline": []
}
// ERROR: 'pipeline' is for aggregate, not find
```

**Empty pipeline:**
```json
{
  "name": "bad_aggregate",
  "collection": "test",
  "type": "aggregate",
  "pipeline": []
}
// ERROR: pipeline must be non-empty
```

**Invalid JSON:**
```json
{
  "name": "bad_json",
  "collection": "test",
  "type": "find"
  "filter": {}
}
// ERROR: Missing comma after "type": "find"
```

## Integration with CLI

Query files are specified via the `--queries` argument (comma-separated):

```bash
biointegrate-execute-queries \
  --config config/queries/mario_queries.yaml \
  --queries queries/q1.txt,queries/q2.txt,queries/q3.txt
```

## Output Files

When using `--output-dir`, each query generates a JSON file named after the query:

```bash
biointegrate-execute-queries \
  --config config/queries/mario_queries.yaml \
  --queries queries/hgnc_find_tp53.txt \
  --output-dir results/
```

Creates: `results/hgnc_find_tp53.json`

## Best Practices

1. **Descriptive Names**: Use clear query names that describe what the query does
   - Good: `"hgnc_find_cancer_genes"`
   - Bad: `"query1"`

2. **Projections**: Use projections to limit returned fields and reduce result size
   - Include only fields you need
   - Exclude large fields like arrays if not needed

3. **Indexes**: Ensure fields used in filters are indexed in MongoDB for performance

4. **Pipeline Order**: In aggregation pipelines, put `$match` stages early to filter data before expensive operations

5. **Testing**: Use `--dry-run` to validate query files before execution:
   ```bash
   biointegrate-execute-queries --config config.yaml --queries q1.txt --dry-run
   ```

## Related Documentation

- [Configuration Format](t2_config_format.md) - YAML config specification
- [T2 Pipeline Overview](t2_pipeline_overview.md) - Overall T2 architecture (optional)
- [MongoDB Query Documentation](https://docs.mongodb.com/manual/tutorial/query-documents/)
- [MongoDB Aggregation Pipeline](https://docs.mongodb.com/manual/core/aggregation-pipeline/)
