# Scripts

This folder contains utility scripts and automation tools for various project tasks.

## Intended Contents

- **Data processing**: Scripts for downloading, cleaning, and transforming data
- **Automation**: Build scripts, deployment scripts, and CI/CD helpers
- **Analysis**: Scripts for running batch analyses or generating reports
- **Maintenance**: Database maintenance, cleanup, and backup scripts
- **Setup**: Installation and environment setup scripts

## Usage

Scripts should be:
- Executable and well-documented
- Include help text or usage instructions
- Handle errors gracefully
- Accept command-line arguments when appropriate
- Be idempotent when possible

## Examples

```bash
# Make script executable
chmod +x scripts/process_data.py

# Run with help
python scripts/process_data.py --help

# Execute script
python scripts/process_data.py --input data/raw --output data/processed
```

## Organization

Group related scripts:
- `data/` - Data-related scripts
- `deploy/` - Deployment and release scripts
- `setup/` - Environment and installation scripts
