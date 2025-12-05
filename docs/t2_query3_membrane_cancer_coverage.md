# T2 – Consulta 3: Proteínas de membrana/cáncer y cobertura de expresión

## Objetivo

Esta consulta parte de **UniProt** y selecciona proteínas humanas localizadas en membrana y/o con anotaciones relacionadas con cáncer. A través de **HGNC** y **GDC** se recupera, para cada proteína/gen, información sobre su expresión en los proyectos **TCGA-LGG** y **TCGA-GBM**, cuantificando cuántos casos presentan expresión por encima de un umbral en TPM (por defecto, 1 TPM).   

---

## Colecciones y campos utilizados

- `uniprot`: se usan `organism.taxonomy_id`, `protein.subcellular_location_cc`, `protein.function_cc`, `go_terms.*` y `projects.{TCGA-LGG,TCGA-GBM}.hgnc_ids`.   
- `hgnc`: enlaza genes y proteínas mediante `uniprot_ids` y contiene, por proyecto, los casos con métricas de expresión (`projects.TCGA-XXX.cases.*.tpm_unstranded`).   
- `gdc`: aporta metadatos de proyecto (`disease_type`, `primary_site`) para TCGA-LGG y TCGA-GBM.   

El enlace principal es `uniprot.uniprot_id → hgnc.uniprot_ids`, y desde HGNC se accede a los casos de expresión anidados por proyecto y caso.

---

## Definición de los filtros de membrana y cáncer

1. **Proteínas humanas**  
   - Se restringe a `organism.taxonomy_id = 9606` para quedarnos solo con proteínas de *Homo sapiens*.   

2. **Localización en membrana**  
   - Se buscan términos que contengan la palabra `"membrane"` (por ejemplo, “plasma membrane”, “Golgi membrane”, “cell membrane”) en:
     - `protein.subcellular_location_cc`
     - `go_terms.cellular_component`  
   - El filtro permite capturar tanto proteínas de membrana plasmática como de otras membranas intracelulares (mitocondria, retículo endoplásmico, Golgi, etc.).   

3. **Anotaciones relacionadas con cáncer (opcional)**  
   - Se exploran:
     - Descripciones funcionales (`protein.function_cc`)  
     - Procesos biológicos (`go_terms.biological_process`)  
   - Se buscan patrones como `cancer`, `tumor`, `carcinoma`, `glioma`, `oncogen` para identificar proteínas con posible implicación en oncogénesis o biología tumoral.   

En el JSON de salida se guardan las cadenas de texto que han disparado estos filtros (campo `membrane_annotations` y `cancer_annotations`), de forma que el usuario puede revisar manualmente las evidencias.

---

## Métricas de cobertura de expresión

Para cada par proteína–gen y para cada proyecto (LGG y GBM) se calculan:

- `n_cases`: número total de casos disponibles en `hgnc.projects.TCGA-XXX.n_cases`.  
- `positive_cases`: número de casos cuyo valor `tpm_unstranded` para ese gen es **> umbral** (por defecto, 1 TPM).  
- `coverage`: proporción de casos positivos, calculada como:

\[
\text{coverage} = 
  \begin{cases}
    \frac{\text{positive\_cases}}{\text{n\_cases}} & \text{si } n\_cases > 0 \\
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
