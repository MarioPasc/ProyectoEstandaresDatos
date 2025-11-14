# Data

This folder contains datasets used in the project. **Do not commit large datasets to version control.**

## Intended Contents

- **raw/**: Original, unprocessed datasets
- **processed/**: Cleaned and processed datasets ready for analysis
- **external/**: Data from external sources or third-party datasets
- **interim/**: Intermediate data files during processing
- **samples/**: Small sample datasets for testing and demonstrations

## Data Management Guidelines

- Add large data files to `.gitignore`
- Document data sources and provenance
- Include data dictionaries or metadata files
- Use consistent naming conventions
- Consider using Git LFS for versioning large files
- Store production data in appropriate external storage (databases, cloud storage)

## Data Format

Prefer standard, open formats:
- CSV for tabular data
- JSON for structured data
- Parquet for large datasets
- XML for hierarchical data requiring validation
