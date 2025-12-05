# T2 – Consulta 3: Proteínas de membrana/cáncer y cobertura de expresión

## Objetivo

Esta consulta parte de la colección **UniProt** y selecciona proteínas humanas localizadas en membrana y/o con anotaciones relacionadas con cáncer. A través de la colección de **genes (HGNC)** y la colección de **proyectos (GDC)** se recupera, para cada proteína/gen, información sobre su expresión en los proyectos **TCGA‑LGG** y **TCGA‑GBM**, cuantificando cuántos casos presentan expresión por encima de un umbral en TPM (por defecto, 1 TPM).

---

## Colecciones y campos utilizados

- **`uniprot`**  
  - Filtros principales en:
    - `organism.taxonomy_id`
    - `protein.subcellular_location_cc`
    - `protein.function_cc`
    - `go_terms.cellular_component`
    - `go_terms.biological_process`
- **`hgnc`**  
  - Enlaza genes y proteínas mediante `uniprot_ids`.  
  - Contiene, por proyecto, los casos con métricas de expresión en:
    - `projects.TCGA-LGG.cases.*.tpm_unstranded`
    - `projects.TCGA-GBM.cases.*.tpm_unstranded`
  - Número total de casos por proyecto:
    - `projects.TCGA-LGG.n_cases`
    - `projects.TCGA-GBM.n_cases`
- **`gdc`**  
  - Aporta metadatos de proyecto:
    - `project_id`
    - `disease_type`
    - `primary_site`

El enlace principal es:

- `uniprot.uniprot_id` → `hgnc.uniprot_ids`  

y desde `hgnc` se accede a los casos de expresión anidados por proyecto y caso.

---

## Definición de los filtros de membrana y cáncer

### 1. Proteínas humanas

Se restringe el análisis a proteínas de *Homo sapiens* utilizando:

- `organism.taxonomy_id = 9606`

Con ello se excluyen entradas de otros organismos presentes en UniProt.

### 2. Localización en membrana

Se consideran proteínas de membrana aquellas que contienen el término `"membrane"` en cualquiera de estos campos:

- `protein.subcellular_location_cc`
- `go_terms.cellular_component`

Este filtro permite capturar tanto proteínas de membrana plasmática como de otras membranas intracelulares (mitocondria, retículo endoplásmico, Golgi, etc.).

En el resultado se guardan las cadenas que cumplen este criterio en el campo:

- `membrane_annotations`

de forma que el usuario pueda revisar las evidencias textuales de localización en membrana.

### 3. Anotaciones relacionadas con cáncer

De forma adicional, la consulta detecta posibles anotaciones relacionadas con cáncer buscando patrones como:

- `cancer`, `tumor`, `carcinoma`, `glioma`, `oncogen`

en:

- `protein.function_cc`
- `go_terms.biological_process`

Las cadenas que contengan estas palabras clave se devuelven en el campo:

- `cancer_annotations`

Esto permite identificar proteínas que, además de ser de membrana, aparecen descritas en contextos tumorales u oncológicos.

---

## Métricas de cobertura de expresión

Para cada par proteína–gen y para cada proyecto (LGG y GBM) se calculan tres métricas:

- `n_cases`: número total de casos disponibles en la colección `hgnc` para ese gen y proyecto (`projects.TCGA-XXX.n_cases`).
- `positive_cases`: número de casos cuyo valor `tpm_unstranded` para ese gen es **mayor que el umbral** (por defecto, 1 TPM).
- `coverage`: proporción de casos positivos, definida como:

\[
\text{coverage} =
  \begin{cases}
    \dfrac{\text{positive\_cases}}{\text{n\_cases}} & \text{si } n\_cases > 0 \\
    \text{null} & \text{en otro caso}
  \end{cases}
\]

Estas métricas se devuelven anidadas en los campos:

```json
"lgg": {
  "n_cases": ...,
  "positive_cases": ...,
  "coverage": ...
},
"gbm": {
  "n_cases": ...,
  "positive_cases": ...,
  "coverage": ...
}
```

lo que permite comparar rápidamente la cobertura de expresión en LGG frente a GBM para cada proteína de membrana seleccionada.

---

## Estructura del resultado

Un documento típico en el JSON de resultados contiene, de forma resumida:

```json
{
  "uniprot_id": "Q8N4A0",
  "entry_name": "GALT4_HUMAN",
  "gene_symbol": "GALNT4",
  "hgnc_id": "HGNC:4126",
  "membrane_annotations": [
    "Golgi apparatus membrane ...",
    "Single-pass type II membrane protein ..."
  ],
  "cancer_annotations": [
    "..."   // solo si se detectan términos relacionados con cáncer
  ],
  "lgg": {
    "n_cases": 5,
    "positive_cases": 3,
    "coverage": 0.6
  },
  "gbm": {
    "n_cases": 4,
    "positive_cases": 2,
    "coverage": 0.5
  },
  "gdc_projects": [
    {
      "project_id": "TCGA-LGG",
      "disease_type": "Brain Lower Grade Glioma",
      "primary_site": "Brain"
    },
    {
      "project_id": "TCGA-GBM",
      "disease_type": "Glioblastoma",
      "primary_site": "Brain"
    }
  ]
}
```

*Nota:* Los valores concretos de `positive_cases` y `coverage` dependen del umbral elegido y de los datos de expresión almacenados en las colecciones.

---

## Discusión e interés biológico

Esta consulta cambia el punto de vista de **gen/caso** a **proteína/función** y permite identificar proteínas de membrana con posible relevancia en gliomas (LGG/GBM). Las proteínas de membrana son especialmente interesantes como posibles **dianas terapéuticas** o **biomarcadores**, ya que suelen ser accesibles a fármacos, anticuerpos y otras moléculas dirigidas.

La combinación de:

1. Anotaciones de localización en membrana,
2. Palabras clave relacionadas con cáncer,
3. Cobertura de expresión en datos de TCGA,

facilita la priorización de candidatos para estudios posteriores, como análisis de redes de señalización, modelos predictivos o validación experimental en contextos de cáncer de cerebro de bajo grado y glioblastoma.
