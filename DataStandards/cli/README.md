# CLI de Descarga de Datos

Este CLI permite descargar datos biomédicos de diferentes fuentes de forma automatizada.

## Instalación

Primero, instala las dependencias necesarias:

```bash
pip install -e .
```

O instala las dependencias manualmente:

```bash
pip install pyyaml requests
```

## Uso

### Sintaxis básica

```bash
python -m DataStandards.cli.data --config <ruta_config> --source <fuente>
```

O si instalaste el paquete:

```bash
datastandards-download --config <ruta_config> --source <fuente>
```

### Opciones

- `--config`: Ruta al fichero de configuración YAML (requerido)
- `--source`: Fuente de datos a descargar (requerido)
  - `gdc`: Descarga datos del Genomic Data Commons
  - `hgnc`: Descarga el conjunto completo de HGNC
  - `uniprot`: Descarga datos de UniProt
  - `all`: Descarga todas las fuentes disponibles
- `--verbose` o `-v`: Activa el modo verbose (opcional)

### Ejemplos

#### Descargar solo datos de GDC

```bash
python -m DataStandards.cli.data --config config/data_config.yaml --source gdc
```

#### Descargar solo datos de HGNC

```bash
python -m DataStandards.cli.data --config config/data_config.yaml --source hgnc
```

#### Descargar solo datos de UniProt

```bash
python -m DataStandards.cli.data --config config/data_config.yaml --source uniprot
```

#### Descargar todas las fuentes

```bash
python -m DataStandards.cli.data --config config/data_config.yaml --source all
```

#### Modo verbose

```bash
python -m DataStandards.cli.data --config config/data_config.yaml --source all --verbose
```

## Configuración

El fichero de configuración debe estar en formato YAML e incluir las secciones para las fuentes que deseas usar:

```yaml
gdc:
  base_url: "https://api.gdc.cancer.gov"
  project_id: "TCGA-LGG"
  # ... otros parámetros

hgnc:
  url: "https://storage.googleapis.com/public-download-files/hgnc/tsv/tsv/hgnc_complete_set.txt"
  output_path: "data/hgnc_complete_set.tsv"
  request_timeout: 60

uniprot:
  url: "https://rest.uniprot.org/uniprotkb/stream"
  query: "organism_id:9606 AND reviewed:true"
  format: "tsv"
  fields: "accession,id,gene_names,protein_name,organism_name,length"
  output_path: "data/uniprot_human_reviewed.tsv"
  request_timeout: 300
```

## Salida

Los datos descargados se guardarán en las rutas especificadas en el fichero de configuración:

- **GDC**: 
  - Manifest: `data/gdc_manifest_tcga_lgg.tsv`
  - Metadatos: `data/gdc_file_metadata_tcga_lgg.tsv`
  - Genes: `data/gdc_genes_tcga_lgg_example.tsv`

- **HGNC**: 
  - `data/hgnc_complete_set.tsv`

- **UniProt**: 
  - `data/uniprot_human_reviewed.tsv`

## Notas

- El directorio `data/` se creará automáticamente si no existe
- Las descargas pueden tardar varios minutos dependiendo del volumen de datos
- Si una fuente falla al usar `--source all`, el proceso continuará con las demás fuentes
