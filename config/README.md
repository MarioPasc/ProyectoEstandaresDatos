# Configuration

This folder contains configuration files for the project and various tools.

## Intended Contents

- **Application config**: Settings and parameters for the DataStandards application
- **Environment configs**: Development, testing, and production configurations
- **Tool configs**: Configuration for linters, formatters, and other development tools
- **Standards definitions**: YAML/JSON files defining data standards and schemas
- **Database configs**: Database connection and schema configurations

## Configuration Files

Examples of configuration files:
- `settings.yaml` - Main application settings
- `standards/` - Directory with data standard definitions
- `logging.yaml` - Logging configuration
- `database.yaml` - Database configuration (template only, no credentials)

## Best Practices

- **Never commit secrets**: Use environment variables for sensitive data
- Provide example/template config files (e.g., `settings.example.yaml`)
- Document all configuration options
- Use appropriate format: YAML for human-readable, JSON for machine-readable
- Validate configuration files at application startup
- Support environment-specific overrides

## Environment Variables

Store sensitive information in environment variables:
- API keys
- Database passwords
- Secret keys
- Production URLs

Use a `.env.example` file to document required environment variables.
