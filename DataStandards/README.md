# DataStandards

This is the main source code folder for the project. It contains all the Python modules and packages that implement the data standards functionality.

## Intended Contents

- **Core modules**: Main implementation of data standards validation and processing
- **Utilities**: Helper functions and common utilities
- **Models**: Data models and schemas
- **Validators**: Validation logic for different data standards
- **Parsers**: Parsers for various data formats
- **API**: API endpoints and interfaces

## Structure

Organize code into logical modules:
- Keep related functionality together in subpackages
- Use clear, descriptive naming conventions
- Include `__init__.py` files for proper package structure
- Document all public APIs with docstrings

---

## Diseño de Colecciones MongoDB

### Estructura de JSONs Exportados

Cada colección se exporta como un **array de documentos individuales**, facilitando consultas con `find()` e índices en MongoDB sin necesidad de `$unwind`:

| Colección | Unidad de Documento | `_id` | Ejemplo |
|-----------|---------------------|-------|---------|
| `gdc_projects` | Proyecto GDC | `project_id` | `"TCGA-LGG"` |
| `hgnc_genes` | Gen HGNC | `hgnc_id` | `"HGNC:11998"` |
| `uniprot` | Entrada UniProt | `uniprot_id` | `"P04637"` |

### Ejemplos de Estructura

**GDC (un documento por proyecto):**
```json
[
  {
    "_id": "TCGA-LGG",
    "project_id": "TCGA-LGG",
    "disease_type": "Brain Lower Grade Glioma",
    "primary_site": "Brain",
    "cases": [
      {
        "case_id": "uuid-case-001",
        "submitter_id": "TCGA-XX-XXXX",
        "files": [...]
      }
    ]
  }
]
```

**HGNC (un documento por gen):**
```json
[
  {
    "_id": "HGNC:11998",
    "hgnc_id": "HGNC:11998",
    "symbol": "TP53",
    "ensembl_gene_id": "ENSG00000141510",
    "uniprot_ids": ["P04637"],
    "projects": {
      "TCGA-LGG": {
        "n_cases": 5,
        "cases": {
          "case-abc123": {"file_id": "...", "unstranded": 1234}
        }
      }
    }
  }
]
```

**UniProt (un documento por entrada):**
```json
[
  {
    "_id": "P04637",
    "uniprot_id": "P04637",
    "entry_name": "P53_HUMAN",
    "reviewed": true,
    "gene": {
      "primary_symbol": "TP53",
      "hgnc_ids": ["HGNC:11998"],
      "ensembl_gene_ids": ["ENSG00000141510"]
    },
    "go_terms": {...},
    "projects": {"TCGA-LGG": {...}}
  }
]
```

### Modelado de Relaciones

**Decisión de diseño**: Usamos **diccionarios indexados por ID** para relaciones anidadas.

| Ventaja | Descripción |
|---------|-------------|
| Acceso directo | `doc.projects["TCGA-LGG"]` sin búsqueda lineal |
| Unicidad garantizada | No hay duplicados por clave |
| Compatibilidad MongoDB | Índices compuestos funcionan bien con esta estructura |

> **Alternativa (arrays)**: Facilitarían `$unwind` para agregaciones, pero requerirían búsquedas lineales para acceso por ID. Hemos priorizado el acceso directo.

### Claves de Enlace entre Colecciones

Las colecciones están interrelacionadas mediante las siguientes claves, permitiendo consultas cross-database para análisis bioinformáticos:

| Relación | Claves de Enlace | Dirección |
|----------|------------------|-----------|
| **HGNC ↔ UniProt** | `hgnc_id`, `ensembl_gene_id`, `uniprot_ids` | Bidireccional |
| **HGNC ↔ GDC** | `project_id`, `case_id`, `file_id` | HGNC contiene refs a GDC |

**Diagrama de relaciones:**
```
┌─────────────────┐     hgnc_id, ensembl_gene_id     ┌─────────────────┐
│   HGNC (genes)  │◄──────────────────────────────────│ UniProt (prot.) │
│                 │      uniprot_ids                  │                 │
└────────┬────────┘                                   └─────────────────┘
         │
         │ project_id, case_id, file_id
         ▼
┌─────────────────┐
│ GDC (proyectos) │
│   └─ casos      │
│      └─ files   │
└─────────────────┘
```

### Ejemplo de Consulta Multi-Colección

**Caso de uso**: Para un paciente con glioma, identificar genes expresados y sus proteínas asociadas.

```
GDC (paciente) → HGNC (genes expresados) → UniProt (proteínas + GO terms)
```

1. Buscar paciente en GDC por `case_id`
2. Buscar genes en HGNC que tengan ese `case_id` en `projects.<project_id>.cases`
3. Para cada gen, buscar proteínas en UniProt por `hgnc_id` en `gene.hgnc_ids`

Este diseño responde a una **pregunta bioinformática real**: explorar expresión génica en gliomas con anotación proteica funcional.
