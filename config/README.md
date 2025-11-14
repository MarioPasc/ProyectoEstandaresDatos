# Configuration

This folder contains configuration files for the DataStandards application and personalized configurations for each team member.

## 📁 Structure

```
config/
├── README.md                    # This file
└── config_files/                # Personal configuration files
    ├── mario_data_config.yaml
    ├── ainhoa_data_config.yaml
    ├── juan_data_config.yaml
    ├── martina_data_config.yaml
    └── teresa_data_config.yaml
```

## 🚀 Quick Start

### Personalizar rutas de salida

> [!CAUTION]
> **DEBES** modificar todas las rutas absolutas en tu archivo `data_config.yaml` para que apunten a tu directorio personal.

Todos los archivos en `config_files/` usan rutas de Mario como plantilla:
```yaml
/home/mpascual/misc/Universidad25-26/Estandares/data/...
```

**Debes cambiar** `/home/mpascual...` por tu ruta personal en los siguientes campos:

> [!WARNING]
> Modifica solo lo que venga antes de los subdirectorios (`data/gdc/`, `data/hgnc/`, `data/uniprot/`).

#### 📍 Sección `gdc`:
```yaml
gdc:
  manifest_output: "/TU_RUTA/data/gdc/gdc_manifest_tcga_lgg.tsv"
  file_metadata_output: "/TU_RUTA/data/gdc/gdc_file_metadata_tcga_lgg.tsv"
  genes_output: "/TU_RUTA/data/gdc/gdc_genes_tcga_lgg_example.tsv"
  
  rnaseq:
    output_dir: "/TU_RUTA/data/gdc/star_counts"
    gene_table_output: "/TU_RUTA/data/gdc/gdc_genes_tcga_lgg.tsv"
```

#### 📍 Sección `hgnc`:
```yaml
hgnc:
  output_path: "/TU_RUTA/data/hgnc/hgnc_complete_set.tsv"
```

#### 📍 Sección `uniprot`:
```yaml
uniprot:
  mapping_output: "/TU_RUTA/data/uniprot/uniprot_mapping_tcga_lgg.tsv"
  metadata_output: "/TU_RUTA/data/uniprot/uniprot_metadata_tcga_lgg.tsv"
```

> [!NOTE]
> Puedes usar cualquier ruta que desees, siempre que tengas permisos de escritura.


## 🔧 Uso

Una vez personalizado tu archivo `data_config.yaml`, puedes ejecutar:

```bash
# Descargar de todas las fuentes
datastandards-download --config config/data_config.yaml --source all

# Descargar datos de una fuente específica (usa el all preferentemente)
datastandards-download --config config/data_config.yaml --source gdc
datastandards-download --config config/data_config.yaml --source hgnc
datastandards-download --config config/data_config.yaml --source uniprot

```

## 🔍 Validación

Para verificar que tu configuración es correcta, puedes:

1. **Verificar sintaxis YAML**: Asegúrate de que el archivo es válido
   ```bash
   python -c "import yaml; yaml.safe_load(open('config/data_config.yaml'))"
   ```

2. **Probar con descarga limitada**: Usa `max_files: 1` en la sección `rnaseq` para una descarga de prueba rápida

## ❓ Preguntas Frecuentes

**P: ¿Puedo cambiar el nombre de los archivos de salida?**  
R: No! Jeje

**P: ¿Qué hago si las descargas fallan?**  
R: Raro... Habla conmigo (Mario) pero comprueba antes que tus rutas estén bien escritas

## 📝 Parámetros que NO debes cambiar

> [!CAUTION]
> Los siguientes parámetros están configurados para el proyecto TCGA-LGG y **NO** deben modificarse:

```yaml
gdc:
  base_url: "https://api.gdc.cancer.gov"
  project_id: "TCGA-LGG"                          # ❌ NO CAMBIAR
  data_category: "Transcriptome Profiling"        # ❌ NO CAMBIAR
  data_type: "Gene Expression Quantification"     # ❌ NO CAMBIAR
  workflow_type: "STAR - Counts"                  # ❌ NO CAMBIAR
  
hgnc:
  url: "https://storage.googleapis.com/..."       # ❌ NO CAMBIAR
  
uniprot:
  base_url: "https://rest.uniprot.org/..."        # ❌ NO CAMBIAR
  organism_id: 9606                                # ❌ NO CAMBIAR (humano)
```

