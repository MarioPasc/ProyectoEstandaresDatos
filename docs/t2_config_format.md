# T2 Configuration Format

Configuration file for `biointegrate-execute-queries` CLI tool.

## Format: YAML

## Required Sections

### `mongo` (required)

MongoDB connection configuration.

**Required fields:**
- `uri` (string): MongoDB connection URI
  - Format: `mongodb://[username:password@]host:port/`
  - Example: `mongodb://localhost:27017/`
  - Example with auth: `mongodb://user:pass@host:27017/`
- `database` (string): Target database name

### `execution` (optional)

Query execution parameters.

**Optional fields:**
- `default_limit` (int | null): Default result limit (null = unlimited)
  - Default: `null`
- `timeout_s` (int): Query timeout in seconds
  - Default: `30`

### `logging` (optional)

Logging configuration.

**Optional fields:**
- `level` (string): Log level (DEBUG, INFO, WARNING, ERROR)
  - Default: `INFO`

## Complete Example

```yaml
mongo:
  uri: "mongodb://localhost:27017/"
  database: "estandares_db"

execution:
  default_limit: 100
  timeout_s: 30

logging:
  level: "INFO"
```

## Minimal Example

```yaml
mongo:
  uri: "mongodb://localhost:27017/"
  database: "estandares_db"
```

## Invalid Examples

**Missing required field:**
```yaml
# ERROR: Missing mongo.database
mongo:
  uri: "mongodb://localhost:27017/"
```

**Invalid YAML syntax:**
```yaml
# ERROR: Invalid indentation
mongo:
uri: "mongodb://localhost:27017/"
  database: "estandares_db"
```

## Integration with CLI

The configuration file is specified via the `--config` argument:

```bash
biointegrate-execute-queries \
  --config config/queries/mario_queries.yaml \
  --queries queries/q1.txt
```

## Overriding Configuration

The `--log-level` CLI flag overrides the `logging.level` setting:

```bash
biointegrate-execute-queries \
  --config config/queries/mario_queries.yaml \
  --queries queries/q1.txt \
  --log-level DEBUG
```

## Security Considerations

- **Credentials in URI**: MongoDB connection URIs can contain username and password.
- **File Permissions**: Ensure config files with credentials have appropriate file permissions (e.g., `chmod 600`).
- **Environment Variables**: For production, consider using environment variable substitution instead of hardcoded credentials.

## Related Documentation

- [Query File Format](t2_query_format.md) - Specification for query files
- [T2 Pipeline Overview](t2_pipeline_overview.md) - Overall T2 architecture (optional)
