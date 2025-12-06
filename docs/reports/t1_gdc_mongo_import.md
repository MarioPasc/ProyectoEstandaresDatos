# Importador MongoDB para Colección GDC (Proyectos, Casos, Muestras y Expresión)

**Issue:** T1 - GDC MongoDB Import Task
**Autor:** DataStandards Team
**Fecha:** 2025-11

---

## Resumen

Este documento describe el pipeline de importación que toma los TSV y ficheros STAR-Counts de GDC y los inserta en una colección MongoDB siguiendo una estructura jerárquica:

```
Proyecto → Casos → Ficheros (con expression_summary)
```

El importador está diseñado para facilitar consultas eficientes y joins con las colecciones de genes y proteínas.

---

## Estructura del Proyecto

### Archivos Implementados

```
ProyectoEstandaresDatos/
├── DataStandards/
│   ├── data/
│   │   └── config.py                         # Dataclasses de configuración (actualizado)
│   └── db/
│       ├── __init__.py                       # Módulo de importadores (nuevo)
│       ├── import_gdc_mongo.py               # Módulo principal de importación (nuevo)
│       └── gdc_config.py                     # Script de configuración (nuevo)
├── config/
│   ├── data/
│   │   └── mario_data_config.yaml            # Config de descarga (actualizado)
│   └── db_mongo/
│       └── mario_mongodb_config.yaml         # Config de MongoDB (nuevo)
├── docs/
│   └── t1_gdc_mongo_import.md               # Este documento
└── pyproject.toml                            # Registro de scripts (actualizado)
```

---

## Configuración

### 1. Archivo de Configuración MongoDB

**Ubicación:** `config/db_mongo/mario_mongodb_config.yaml`

```yaml
mongodb:
  mongo_uri: "mongodb://localhost:27017/"
  database_name: "estandares_db"
  collection_name: "gdc_cases"

gdc:
  # Rutas a ficheros de entrada TSV
  manifest_path: "/ruta/data/gdc/gdc_manifest_tcga_lgg.tsv"
  metadata_path: "/ruta/data/gdc/gdc_file_metadata_tcga_lgg.tsv"
  genes_path: "/ruta/data/gdc/gdc_genes_tcga_lgg.tsv"
  star_counts_dir: "/ruta/data/gdc/star_counts"

  # Información del proyecto
  project_id: "TCGA-LGG"
  disease_type: "Brain Lower Grade Glioma"
  primary_site: "Brain"
  data_category: "Transcriptome Profiling"

options:
  drop_collection: false      # Eliminar colección antes de importar
  process_expression: true    # Procesar ficheros STAR-Counts
  max_files_to_process: null  # Límite de ficheros (null = todos)
  verbose: true               # Mensajes detallados
  save_as_json: "/ruta/gdc_collection_export.json"  # Exportar colección como JSON
```

### 2. Actualización de mario_data_config.yaml

Se añadió una sección `mongodb_T1` para compatibilidad con los importadores existentes:

```yaml
mongodb_T1:
  mongo_uri: "mongodb://localhost:27017/"
  database_name: "estandares_db"
  collections:
    genes: "genes"
    proteins: "proteins"
    gdc_cases: "gdc_cases"
```

---

## Pipeline de Importación

### Diagrama de Flujo

```
┌──────────────────────────┐
│  1. Descargar Datos GDC  │
│  (datastandards-download)│
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│  2. Cargar TSVs          │
│  - manifest              │
│  - metadata              │
│  - genes                 │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│  3. Construir Documento  │
│  - Agrupar por casos     │
│  - Enlazar ficheros      │
│  - Calcular stats        │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│  4. Insertar en MongoDB  │
│  (upsert en colección)   │
└──────────────────────────┘
```

### Paso 1: Descargar Datos GDC

Antes de ejecutar el importador, asegúrate de haber descargado los datos GDC:

```bash
datastandards-download --config config/data/mario_data_config.yaml --source gdc
```

Esto genera:
- `gdc_manifest_tcga_lgg.tsv` (lista de ficheros)
- `gdc_file_metadata_tcga_lgg.tsv` (relación caso-fichero)
- `gdc_genes_tcga_lgg.tsv` (genes del proyecto)
- `star_counts/*.rna_seq.augmented_star_gene_counts.tsv` (expresión génica)

### Paso 2: Ejecutar Importador

```bash
# Importación básica
datastandards-import-gdc --config config/db_mongo/mario_mongodb_config.yaml

# Rehacer la carga (eliminar colección primero)
datastandards-import-gdc --config config/db_mongo/mario_mongodb_config.yaml --drop-collection

# Importar solo metadatos (sin procesar expresión)
datastandards-import-gdc --config config/db_mongo/mario_mongodb_config.yaml --no-expression

# Procesar solo los primeros 10 ficheros (testing)
datastandards-import-gdc --config config/db_mongo/mario_mongodb_config.yaml --max-files 10

# Modo silencioso
datastandards-import-gdc --config config/db_mongo/mario_mongodb_config.yaml --quiet

# Guardar colección como JSON en ruta personalizada
datastandards-import-gdc --config config/db_mongo/mario_mongodb_config.yaml --save-json /ruta/custom_export.json

# No guardar como JSON (ignorar configuración YAML)
datastandards-import-gdc --config config/db_mongo/mario_mongodb_config.yaml --no-save-json
```

### Exportación a JSON

El importador puede exportar automáticamente la colección MongoDB a un archivo JSON después de una importación exitosa. Esto es útil para:

- **Backup de datos**: Mantener una copia en formato JSON
- **Compartir datos**: Facilitar el intercambio de datos sin necesidad de MongoDB
- **Análisis externo**: Usar herramientas que trabajan con JSON
- **Versionado**: Guardar snapshots de los datos en diferentes momentos

**Configuración:**

1. **Desde YAML**: Especifica la ruta en `config/db_mongo/mario_mongodb_config.yaml`:
   ```yaml
   options:
     save_as_json: "/ruta/export.json"
   ```

2. **Desde CLI**: Usa las opciones `--save-json` o `--no-save-json`:
   ```bash
   # Exportar a ruta específica (sobrescribe YAML)
   datastandards-import-gdc --config config.yaml --save-json /tmp/export.json

   # Desactivar exportación (sobrescribe YAML)
   datastandards-import-gdc --config config.yaml --no-save-json
   ```

**Formato del JSON exportado:**

El archivo JSON contiene un array con todos los documentos de la colección. Los ObjectIds de MongoDB se convierten automáticamente a strings para compatibilidad JSON.

```json
[
  {
    "_id": "TCGA-LGG",
    "project_id": "TCGA-LGG",
    "disease_type": "Brain Lower Grade Glioma",
    "cases": [ ... ]
  }
]
```

---

## Esquema de Datos MongoDB

### Estructura del Documento

La colección `gdc_cases` contiene **un documento por proyecto** con la siguiente estructura jerárquica:

```json
{
  "_id": "TCGA-LGG",
  "project_id": "TCGA-LGG",
  "disease_type": "Brain Lower Grade Glioma",
  "primary_site": "Brain",
  "data_category": "Transcriptome Profiling",
  "cases": [
    {
      "case_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      "submitter_id": "TCGA-CS-6665",
      "files": [
        {
          "file_id": "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy",
          "file_name": "abcd1234.rna_seq.augmented_star_gene_counts.tsv",
          "file_size": 1845678,
          "md5sum": "a1b2c3d4e5f6...",
          "state": "released",
          "expression_summary": {
            "n_genes": 60660,
            "stats": {
              "mean": 1234.56,
              "median": 89.0,
              "std": 5678.90
            }
          }
        }
      ]
    }
  ]
}
```

### Descripción de Campos

#### Nivel 1: Proyecto
- `_id` (string): ID del proyecto (clave primaria)
- `project_id` (string): ID del proyecto (duplicado para consistencia)
- `disease_type` (string): Tipo de enfermedad
- `primary_site` (string): Sitio anatómico primario
- `data_category` (string): Categoría de datos

#### Nivel 2: Casos (array)
- `case_id` (string): UUID único del caso **[Campo clave para joins]**
- `submitter_id` (string): ID legible del caso (ej. TCGA-XX-YYYY)
- `files` (array): Array de ficheros asociados al caso

#### Nivel 3: Ficheros (array)
- `file_id` (string): UUID único del fichero **[Campo clave para joins]**
- `file_name` (string): Nombre del fichero
- `file_size` (int): Tamaño en bytes
- `md5sum` (string): Checksum MD5
- `state` (string): Estado del fichero (ej. "released")
- `expression_summary` (object): Resumen de expresión génica

#### Nivel 4: Expression Summary
- `n_genes` (int): Número total de genes en el fichero
- `stats` (object): Estadísticas de expresión
  - `mean` (float): Media de los valores de expresión
  - `median` (float): Mediana de los valores de expresión
  - `std` (float): Desviación estándar

---

## Ejemplos de Consultas MongoDB

### Consultas Básicas

#### 1. Obtener información del proyecto

```javascript
db.gdc_cases.findOne(
  { "_id": "TCGA-LGG" },
  { "disease_type": 1, "primary_site": 1, "cases": { $size: "$cases" } }
)
```

#### 2. Contar número total de casos

```javascript
db.gdc_cases.aggregate([
  { $match: { "_id": "TCGA-LGG" } },
  { $project: { n_cases: { $size: "$cases" } } }
])
```

#### 3. Listar todos los casos con sus IDs

```javascript
db.gdc_cases.aggregate([
  { $match: { "_id": "TCGA-LGG" } },
  { $unwind: "$cases" },
  { $project: {
      _id: 0,
      case_id: "$cases.case_id",
      submitter_id: "$cases.submitter_id",
      n_files: { $size: "$cases.files" }
  }}
])
```

#### 4. Obtener ficheros de un caso específico

```javascript
db.gdc_cases.aggregate([
  { $match: { "_id": "TCGA-LGG" } },
  { $unwind: "$cases" },
  { $match: { "cases.submitter_id": "TCGA-CS-6665" } },
  { $unwind: "$cases.files" },
  { $project: {
      _id: 0,
      file_id: "$cases.files.file_id",
      file_name: "$cases.files.file_name",
      file_size: "$cases.files.file_size"
  }}
])
```

### Consultas de Expresión Génica

#### 5. Estadísticas de expresión por fichero

```javascript
db.gdc_cases.aggregate([
  { $match: { "_id": "TCGA-LGG" } },
  { $unwind: "$cases" },
  { $unwind: "$cases.files" },
  { $match: { "cases.files.expression_summary": { $ne: null } } },
  { $project: {
      _id: 0,
      case_id: "$cases.case_id",
      file_name: "$cases.files.file_name",
      n_genes: "$cases.files.expression_summary.n_genes",
      mean_expression: "$cases.files.expression_summary.stats.mean",
      median_expression: "$cases.files.expression_summary.stats.median"
  }}
])
```

#### 6. Ficheros con alta expresión media

```javascript
db.gdc_cases.aggregate([
  { $match: { "_id": "TCGA-LGG" } },
  { $unwind: "$cases" },
  { $unwind: "$cases.files" },
  { $match: { "cases.files.expression_summary.stats.mean": { $gt: 1000 } } },
  { $project: {
      _id: 0,
      case_id: "$cases.case_id",
      file_name: "$cases.files.file_name",
      mean_expression: "$cases.files.expression_summary.stats.mean"
  }},
  { $sort: { mean_expression: -1 } }
])
```

### Consultas para Joins con Genes/Proteínas

#### 7. Preparar file_ids para join con genes

```javascript
// Obtener lista de file_ids para usar en búsquedas posteriores
db.gdc_cases.aggregate([
  { $match: { "_id": "TCGA-LGG" } },
  { $unwind: "$cases" },
  { $unwind: "$cases.files" },
  { $group: {
      _id: null,
      file_ids: { $push: "$cases.files.file_id" }
  }},
  { $project: { _id: 0, file_ids: 1 } }
])
```

#### 8. Buscar casos por case_id (para join con otras colecciones)

```javascript
// Esta consulta retorna el case_id que puede usarse para joins
db.gdc_cases.aggregate([
  { $match: { "_id": "TCGA-LGG" } },
  { $unwind: "$cases" },
  { $match: { "cases.case_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" } },
  { $project: {
      _id: 0,
      case_id: "$cases.case_id",
      submitter_id: "$cases.submitter_id",
      files: "$cases.files"
  }}
])
```

---

## Campos Clave para Joins

Los siguientes campos están diseñados para facilitar joins con otras colecciones:

| Campo | Ubicación | Uso en Joins |
|-------|-----------|--------------|
| `project_id` | Raíz | Filtrar por proyecto |
| `case_id` | `cases[]` | Enlazar con datos clínicos/muestras |
| `file_id` | `cases[].files[]` | Enlazar con datos de expresión génica individual |
| `file_name` | `cases[].files[]` | Referencia a ficheros STAR-Counts |

### Ejemplo de Join Conceptual (Python)

```python
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client["estandares_db"]

# 1. Obtener file_id de un caso
gdc_doc = db.gdc_cases.find_one({"_id": "TCGA-LGG"})
case = next((c for c in gdc_doc["cases"] if c["submitter_id"] == "TCGA-CS-6665"), None)
file_ids = [f["file_id"] for f in case["files"]]

# 2. Usar file_id para buscar genes relacionados (si existiera esa colección)
# Esto es un ejemplo conceptual para T2/T3
# genes = db.gene_expression.find({"file_id": {"$in": file_ids}})
```

---

## Ampliaciones Futuras (T2/T3)

En las siguientes iteraciones del proyecto, se pueden añadir:

### 1. Expresión Génica Detallada
Actualmente, `expression_summary` solo contiene estadísticas globales. Se puede ampliar para incluir:

```json
"expression_summary": {
  "n_genes": 60660,
  "stats": { ... },
  "top_expressed_genes": [
    { "gene_symbol": "TP53", "ensembl_id": "ENSG00000141510", "count": 12345 },
    { "gene_symbol": "IDH1", "ensembl_id": "ENSG00000138413", "count": 10234 }
  ]
}
```

### 2. Colección Separada de Expresión Génica
Para datasets grandes, puede ser más eficiente crear una colección separada:

```javascript
// Colección: gene_expression
{
  "_id": ObjectId("..."),
  "file_id": "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy",
  "case_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "project_id": "TCGA-LGG",
  "gene_id": "ENSG00000141510",
  "gene_symbol": "TP53",
  "counts": {
    "unstranded": 12345,
    "stranded_first": 12000,
    "stranded_second": 345
  }
}
```

### 3. Índices para Optimización

```javascript
// Índices recomendados
db.gdc_cases.createIndex({ "cases.case_id": 1 })
db.gdc_cases.createIndex({ "cases.files.file_id": 1 })
db.gdc_cases.createIndex({ "cases.submitter_id": 1 })

// Para colección de expresión génica (futura)
db.gene_expression.createIndex({ "file_id": 1, "gene_id": 1 })
db.gene_expression.createIndex({ "case_id": 1 })
db.gene_expression.createIndex({ "gene_symbol": 1 })
```

---

## Solución de Problemas

### Error: Fichero de configuración no encontrado

```
Error: Archivo de configuración no encontrado: config/db_mongo/mario_mongodb_config.yaml
```

**Solución:** Verifica que el archivo existe y la ruta es correcta. Puedes especificar una ruta diferente con `--config`.

### Error: Manifest no encontrado

```
FileNotFoundError: Manifest no encontrado: /ruta/data/gdc/gdc_manifest_tcga_lgg.tsv
```

**Solución:** Asegúrate de haber descargado los datos GDC primero:
```bash
datastandards-download --config config/data/mario_data_config.yaml --source gdc
```

### Error: Conexión a MongoDB

```
Error conectando a MongoDB: [Errno 111] Connection refused
```

**Solución:** Verifica que MongoDB esté corriendo:
```bash
# Iniciar MongoDB
sudo systemctl start mongodb

# Verificar estado
sudo systemctl status mongodb
```

### Ficheros STAR-Counts comprimidos

Si los ficheros STAR-Counts están comprimidos (`.gz`), el importador los saltará por defecto. Para procesarlos:

1. **Opción 1:** Descomprimir manualmente
```bash
cd data/gdc/star_counts
gunzip *.gz
```

2. **Opción 2:** Usar la opción de descarga con descompresión automática (actualizar `mario_data_config.yaml`):
```yaml
gdc:
  rnaseq:
    decompress_downloads: true
```

---

## Resumen de Comandos

```bash
# 1. Descargar datos GDC
datastandards-download --config config/data/mario_data_config.yaml --source gdc

# 2. Importar a MongoDB (con exportación JSON automática)
datastandards-import-gdc --config config/db_mongo/mario_mongodb_config.yaml

# 3. Importar sin exportar JSON
datastandards-import-gdc --config config/db_mongo/mario_mongodb_config.yaml --no-save-json

# 4. Exportar a ruta personalizada
datastandards-import-gdc --config config/db_mongo/mario_mongodb_config.yaml --save-json /tmp/export.json

# 5. Verificar importación (desde mongo shell)
mongosh
> use estandares_db
> db.gdc_cases.findOne()
> db.gdc_cases.countDocuments()

# 6. Verificar JSON exportado
cat /ruta/gdc_collection_export.json | python -m json.tool | head -50

# 7. Reinstalar paquete después de cambios
pip install -e .
```

---

## Relación con HGNC

### Campo de Vinculación: ensembl_gene_id

La relación entre las colecciones GDC y HGNC se establece a través del identificador **`ensembl_gene_id`**, que actúa como clave foránea natural entre ambas bases de datos.

#### Flujo de Datos

```
GDC (STAR-Counts)
    ↓
gene_id (con versión: ENSG00000000003.15)
    ↓
ensembl_gene_id (sin versión: ENSG00000000003)
    ↓
HGNC (genes estandarizados)
    ↓
hgnc_id, symbol, uniprot_ids
```

### Estrategia de Vinculación Recomendada

Mantener las colecciones **separadas** y unirlas mediante consultas MongoDB:

**Colección GDC** (estructura actual sin cambios):
```json
{
  "_id": "TCGA-LGG",
  "project_id": "TCGA-LGG",
  "disease_type": "Brain Lower Grade Glioma",
  "cases": [
    {
      "case_id": "xxx",
      "files": [
        {
          "file_id": "yyy",
          "expression_summary": {
            "n_genes": 60660
            // Referencia implícita a genes por ensembl_gene_id
          }
        }
      ]
    }
  ]
}
```

**Colección HGNC** (futura):
```json
{
  "_id": "HGNC:5",
  "hgnc_id": "HGNC:5",
  "symbol": "TSPAN6",
  "ensembl_gene_id": "ENSG00000000003",  // ← CLAVE DE RELACIÓN
  "uniprot_ids": ["O43657"],
  "projects": {
    "TCGA-LGG": {
      "case_ids": [
        "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy"
      ],
      "n_cases": 2,
      "file_ids": [
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
      ]
    }
    // Otros proyectos (TCGA-GBM, etc.) se añadirían aquí
  }
}
```

**Ventajas de esta estrategia:**
- ✅ Sigue principios de diseño MongoDB
- ✅ Evita redundancia (no duplica 60,660 IDs en cada proyecto)
- ✅ Facilita mantenimiento (actualizaciones en HGNC no afectan GDC)
- ✅ Permite queries bidireccionales eficientes
- ✅ **Granularidad por caso**: Acceso directo a casos específicos donde se expresa el gen
- ✅ **Trazabilidad completa**: Enlaces directos a `case_id` y `file_id` en GDC
- ✅ **Multi-proyecto**: Estructura escalable para múltiples proyectos TCGA

#### Consultas de Ejemplo para Unir Colecciones

**1. Obtener genes expresados en el proyecto TCGA-LGG:**
```javascript
db.hgnc.find({ "projects.TCGA-LGG": { $exists: true } })
```

**2. Obtener genes expresados en un caso específico:**
```javascript
db.hgnc.find({ 
  "projects.TCGA-LGG.case_ids": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" 
})
```

**3. Contar cuántos casos expresan un gen específico:**
```javascript
db.hgnc.findOne(
  { "symbol": "TP53" },
  { "projects.TCGA-LGG.n_cases": 1 }
)
```

**4. Pipeline de agregación GDC → HGNC → UniProt con casos específicos:**
```javascript
db.hgnc.aggregate([
  // Filtrar genes del proyecto con al menos 100 casos
  { $match: { 
      "projects.TCGA-LGG": { $exists: true },
      "projects.TCGA-LGG.n_cases": { $gte: 100 }
  }},
  
  // Unir con proteínas UniProt
  { $lookup: {
      from: "uniprot",
      localField: "uniprot_ids",
      foreignField: "uniprot_id",
      as: "proteins"
  }},
  
  // Proyectar campos relevantes
  { $project: {
      gene_symbol: "$symbol",
      hgnc_id: 1,
      ensembl_gene_id: 1,
      n_cases: "$projects.TCGA-LGG.n_cases",
      example_case_ids: { $slice: ["$projects.TCGA-LGG.case_ids", 5] },
      n_proteins: { $size: "$proteins" },
      protein_names: "$proteins.protein_name"
  }}
])
```

**5. Buscar información completa de un caso desde HGNC:**
```javascript
// Paso 1: Obtener genes expresados en un caso específico
const caseId = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx";
const genes = db.hgnc.find({ 
  "projects.TCGA-LGG.case_ids": caseId 
}, {
  symbol: 1,
  ensembl_gene_id: 1,
  hgnc_id: 1
});

// Paso 2: Buscar información del caso en GDC
db.gdc_cases.aggregate([
  { $match: { "_id": "TCGA-LGG" } },
  { $unwind: "$cases" },
  { $match: { "cases.case_id": caseId } },
  { $project: {
      case_id: "$cases.case_id",
      submitter_id: "$cases.submitter_id",
      n_files: { $size: "$cases.files" },
      files: "$cases.files"
  }}
])
```

**6. Genes comunes entre múltiples casos:**
```javascript
// Encontrar genes expresados en al menos 2 casos específicos
const targetCases = [
  "case-uuid-1",
  "case-uuid-2"
];

db.hgnc.find({
  "projects.TCGA-LGG.case_ids": { $all: targetCases }
}, {
  symbol: 1,
  ensembl_gene_id: 1,
  "projects.TCGA-LGG.n_cases": 1
})
```

**7. Estadísticas de expresión génica por proyecto:**
```javascript
db.hgnc.aggregate([
  { $match: { "projects.TCGA-LGG": { $exists: true } } },
  { $group: {
      _id: null,
      total_genes: { $sum: 1 },
      avg_cases_per_gene: { $avg: "$projects.TCGA-LGG.n_cases" },
      max_cases: { $max: "$projects.TCGA-LGG.n_cases" },
      min_cases: { $min: "$projects.TCGA-LGG.n_cases" }
  }}
])
```

### Índices Recomendados para Joins Eficientes

```javascript
// Colección GDC
db.gdc_cases.createIndex({ "project_id": 1 })
db.gdc_cases.createIndex({ "cases.case_id": 1 })
db.gdc_cases.createIndex({ "cases.submitter_id": 1 })
db.gdc_cases.createIndex({ "cases.files.file_id": 1 })

// Colección HGNC (futura)
db.hgnc.createIndex({ "ensembl_gene_id": 1 })
db.hgnc.createIndex({ "symbol": 1 })
db.hgnc.createIndex({ "projects.TCGA-LGG.case_ids": 1 })
db.hgnc.createIndex({ "projects.TCGA-LGG.file_ids": 1 })
db.hgnc.createIndex({ "projects.TCGA-LGG.n_cases": 1 })
db.hgnc.createIndex({ "uniprot_ids": 1 })

// Índice compuesto para búsquedas multi-proyecto (si se añaden más proyectos)
db.hgnc.createIndex({ 
  "projects.TCGA-LGG.n_cases": 1,
  "projects.TCGA-GBM.n_cases": 1 
})

// Colección de expresión génica detallada (futura)
db.gene_expression.createIndex({ "file_id": 1, "ensembl_gene_id": 1 })
db.gene_expression.createIndex({ "project_id": 1, "ensembl_gene_id": 1 })
db.gene_expression.createIndex({ "case_id": 1 })
```

### Construcción de la Colección HGNC desde GDC

Para poblar la colección HGNC con la estructura de proyectos propuesta, se necesitará:

**1. Extraer el mapeo `ensembl_gene_id` → `case_ids` + `file_ids` desde los ficheros STAR-Counts:**

```python
# Pseudocódigo del proceso
gene_to_cases = {}

for case in gdc_document["cases"]:
    case_id = case["case_id"]
    
    for file in case["files"]:
        file_id = file["file_id"]
        star_counts_path = f"{star_counts_dir}/{file['file_name']}"
        
        # Leer genes expresados en el fichero
        df = pd.read_csv(star_counts_path, sep='\t')
        
        for _, row in df.iterrows():
            ensembl_id = row["gene_id"].split(".")[0]  # Sin versión
            
            if ensembl_id not in gene_to_cases:
                gene_to_cases[ensembl_id] = {
                    "case_ids": set(),
                    "file_ids": set()
                }
            
            gene_to_cases[ensembl_id]["case_ids"].add(case_id)
            gene_to_cases[ensembl_id]["file_ids"].add(file_id)
```

**2. Combinar con metadatos HGNC:**

```python
# Para cada gen en HGNC
hgnc_doc = {
    "_id": hgnc_id,
    "hgnc_id": hgnc_id,
    "symbol": symbol,
    "ensembl_gene_id": ensembl_id,
    "uniprot_ids": uniprot_ids,
    "projects": {
        "TCGA-LGG": {
            "case_ids": list(gene_to_cases[ensembl_id]["case_ids"]),
            "n_cases": len(gene_to_cases[ensembl_id]["case_ids"]),
            "file_ids": list(gene_to_cases[ensembl_id]["file_ids"])
        }
    }
}
```

**Nota:** Este proceso será implementado en el importador HGNC (próxima tarea) que procesará tanto los datos HGNC como los ficheros STAR-Counts de GDC para construir las referencias cruzadas.

---

## Referencias

- **Issue T1:** Importador MongoDB para colección GDC
- **Documentación GDC API:** https://docs.gdc.cancer.gov/API/
- **PyMongo Documentation:** https://pymongo.readthedocs.io/
- **MongoDB Aggregation:** https://www.mongodb.com/docs/manual/aggregation/
- **HGNC Database:** https://www.genenames.org/

---

## Contacto

Para preguntas o problemas con el importador, contacta al equipo de DataStandards o abre un issue en el repositorio.
