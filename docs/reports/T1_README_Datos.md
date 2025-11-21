## Descripción técnico-científica del pipeline GDC → HGNC → UniProt

### 1. Visión general

El flujo completo que se ha implementado conecta tres recursos biomédicos de referencia:

1. **NCI Genomic Data Commons (GDC)**: repositorio de datos genómicos y clínicos armonizados procedentes de proyectos como TCGA.([GA4GH][1])
2. **HGNC (HUGO Gene Nomenclature Committee)**: base de datos de nomenclatura génica humana que define símbolos, identificadores estables (`hgnc_id`) y mapeos a otros recursos.([genenames.org][2])
3. **UniProtKB**: base de datos de secuencias y anotación funcional de proteínas, accesible programáticamente a través de la API REST `uniprotkb`.([UniProt][3])

El objetivo del pipeline es:

* Partir de un **proyecto transcriptómico de cáncer** (TCGA-LGG) en GDC.([portal.gdc.cancer.gov][4])
* Extraer el **universo de genes Ensembl** cuantificados en dicho proyecto.
* Mapear esos genes a **entidades génicas estandarizadas** en HGNC.
* Traducirlos a **proteínas UniProt** y recuperar anotación funcional y subcelular relevante.

Este flujo prepara los datos para su integración en MongoDB, cumpliendo los requisitos de:

* ≥ 3 colecciones interconectadas (GDC, HGNC, UniProt).
* ≥ 3 niveles de anidamiento en cada colección.
* Población suficiente para consultas biológicamente interesantes.

---

### 2. Genomic Data Commons (GDC)

#### 2.1. Naturaleza de la base de datos

La NCI Genomic Data Commons es una plataforma de compartición de datos oncológicos que almacena y armoniza datos genómicos y clínicos de múltiples proyectos (TCGA, TARGET, etc.), aplicando pipelines de análisis uniformes.([GA4GH][1])

El proyecto **TCGA-LGG (Lower Grade Glioma)** se centra en gliomas de bajo grado y forma parte del programa TCGA, que ha caracterizado molecularmente miles de tumores.([portal.gdc.cancer.gov][4])

En particular, el pipeline de expresión mRNA del GDC cuantifica la expresión génica a nivel de **STAR raw counts** y genera ficheros `*.rna_seq.augmented_star_gene_counts.tsv` con conteos, TPM y FPKM para cada gen anotado en GENCODE sobre GRCh38.([docs.gdc.cancer.gov][5])

#### 2.2. Objetivo en este proyecto

En este trabajo, GDC se utiliza para:

* Obtener el **listado completo de ficheros de expresión** STAR-Counts del proyecto TCGA-LGG.
* Extraer la **relación proyecto → caso → fichero de expresión**.
* Derivar el **conjunto de genes Ensembl** realmente cuantificados en el proyecto (60 660 genes).

Esto convierte GDC en la fuente transcriptómica de partida sobre la que se articularán las conexiones génicas y proteicas.

#### 2.3. Ficheros de salida del módulo GDC

A partir de la API de GDC se han generado los siguientes artefactos:

1. **`gdc_manifest_tcga_lgg.tsv`**

   * 534 filas (un fichero por fila).
   * Columnas:

     * `file_id`: UUID interno de GDC para el fichero.
     * `file_name`: nombre del fichero (p.ej. `*.rna_seq.augmented_star_gene_counts.tsv`).
     * `file_size`: tamaño en bytes.
     * `id`: identificador redundante del recurso.
     * `md5sum`: hash MD5 para verificación de integridad.
     * `state`: estado del fichero en GDC (por ejemplo, `released`).
   * Este manifest es análogo al generado por herramientas como `gdcdata` en Bioconductor.([bioconductor.github.io][6])

2. **`gdc_file_metadata_tcga_lgg.tsv`**

   * 534 filas, columnas:

     * `cases.0.case_id`: identificador interno del caso en GDC.
     * `cases.0.submitter_id`: identificador de envío (p.ej. `TCGA-XX-YYYY`).
     * `file_id`, `file_name`: claves para enlazar con el manifest.
     * `id`: identificador del recurso.
   * Permite construir el enlace **proyecto → caso → fichero de expresión**.

3. **Ficheros STAR-Counts individuales (`*.rna_seq.augmented_star_gene_counts.tsv`)**

   * 5 ficheros descargados (20 MB en total), cada uno con:

     * 60 664 filas (genes) × 9 columnas.
     * Columnas comunes:

       * `gene_id` (ID Ensembl con versión, p.ej. `ENSG00000000003.15`).
       * `gene_name` (símbolo).
       * `gene_type` (tipo GENCODE, p.ej. `protein_coding`, `lncRNA`).
       * `unstranded`, `stranded_first`, `stranded_second` (conteos).
       * `tpm_unstranded`, `fpkm_unstranded`, `fpkm_uq_unstranded` (métricas de expresión normalizadas).([docs.gdc.cancer.gov][5])

4. **`gdc_genes_tcga_lgg.tsv`** (tabla de genes del proyecto)

   * 60 660 filas, 2 columnas:

     * `ensembl_gene_id_gdc`: ID Ensembl tal como aparece en `gene_id` (con versión).
     * `ensembl_gene_id`: ID Ensembl normalizado sin versión (p.ej. `ENSG00000000003`).
   * Se obtiene extrayendo la columna `gene_id` de un fichero STAR-Counts de referencia y limpiando la versión.

#### 2.4. Niveles de agregación previstos para la colección GDC

Una colección orientada a GDC en MongoDB puede estructurarse con ≥ 3 niveles de anidamiento:

1. **Nivel 1 – Proyecto**

   * Documento raíz con `project_id: "TCGA-LGG"`, `disease_type`, `primary_site`, etc.([portal.gdc.cancer.gov][4])

2. **Nivel 2 – Casos**

   * Array `cases` con elementos que combinan `case_id` y `submitter_id`.
   * Para cada caso, se pueden incluir metadatos adicionales derivados de GDC (tipo de muestra, etc.).([Nature][7])

3. **Nivel 3 – Muestras / Ficheros de expresión**

   * Dentro de cada caso, array `samples` o `files` con:

     * `file_id`, `file_name`, `sample_type`.
     * Resumen de expresión (`n_genes`, valores globales, etc.).

4. **Nivel 4 – Resumen génico (opcional)**

   * Para ciertos genes de interés, se podrían añadir subdocumentos con estadísticas de expresión por caso (p.ej. `IDH1`, `TP53`), sin necesidad de almacenar las 60 660 filas completas.

Con ello, la colección GDC presenta una jerarquía **proyecto → caso → fichero/muestra → resumen génico**, compatible con consultas clínicas y transcriptómicas.

---

### 3. HGNC (HUGO Gene Nomenclature Committee)

#### 3.1. Naturaleza de la base de datos

HGNC mantiene el sistema oficial de nomenclatura de genes humanos, asignando para cada locus un identificador `hgnc_id`, un símbolo aprobado y un nombre estandarizado, además de múltiples sinónimos y mapeos a otras bases (Ensembl, NCBI, UniProt, etc.).([genenames.org][2])

El fichero **`hgnc_complete_set`** contiene **todos los “gene symbol reports” aprobados** sobre la referencia GRCh38, incluyendo loci proteicos, ncRNA y pseudogenes.([genenames.org][8])

#### 3.2. Objetivo en este proyecto

HGNC se emplea como **capa de normalización génica** entre:

* Los Ensembl gene IDs derivados del GDC (`gdc_genes_tcga_lgg.tsv`).
* Los identificadores de proteínas de UniProt.

En concreto, utilizamos HGNC para:

* Mapear `ensembl_gene_id` → (`hgnc_id`, `symbol`, `name`).
* Filtrar genes **protein-coding** (`locus_group = "protein-coding gene"`).
* Extraer los `uniprot_ids` asociados a cada gen humano cuantificado en el proyecto.

#### 3.3. Fichero de salida del módulo HGNC

No se generan sub-ficheros adicionales: trabajamos directamente sobre:

* **`hgnc_complete_set.tsv`**

  * 44 618 filas, 54 columnas.
  * Columnas relevantes para este pipeline:

    * Identificación y nomenclatura:

      * `hgnc_id` (ID estable HGNC).
      * `symbol` (símbolo aprobado).
      * `name` (nombre del gen).
      * `status` (p.ej. “Approved”).
      * `locus_group` (p.ej. `"protein-coding gene"`, `"non-coding RNA"`).
      * `locus_type` (p.ej. `"gene with protein product"`, `"RNA, long non-coding"`).([genenames.org][8])
    * Posición y anotación:

      * `location`, `location_sortable`.
    * Identificadores cruzados:

      * `ensembl_gene_id` (IDs Ensembl, potencialmente múltiples).
      * `entrez_id`, `refseq_accession`, `ucsc_id`, etc.
      * `uniprot_ids` (uno o varios accesos UniProt por gen).([genenames.org][8])

A partir de este fichero se crea el **subconjunto relevante**: genes del proyecto GDC con `ensembl_gene_id` en `gdc_genes_tcga_lgg.tsv`, `locus_group = "protein-coding gene"` y `uniprot_ids` no vacíos.

#### 3.4. Niveles de agregación previstos para la colección HGNC

La correspondiente colección génica en MongoDB puede diseñarse con la siguiente jerarquía:

1. **Nivel 1 – Gen (entidad HGNC)**

   * Documento raíz con `hgnc_id`, `symbol`, `name`, `locus_group`, `locus_type`.

2. **Nivel 2 – Identificadores cruzados y nomenclatura extendida**

   * Subdocumento `identifiers` con:

     * `ensembl_gene_ids`, `entrez_id`, `refseq`, `ucsc_id`, etc.
   * Subdocumento `synonyms` con:

     * `alias_symbol`, `prev_symbol`, `alias_name`, `prev_name`.

3. **Nivel 3 – Mapas a recursos externos**

   * Subdocumento `external_links` con:

     * `uniprot_ids` (lista de accesos),
     * `omim_id`, `orphanet`, `cosmic`, etc., cuando estén presentes.([genenames.org][8])

4. **Nivel 4 – Proyectos GDC relacionados (opcional)**

   * Array `projects` donde se listan los proyectos GDC en los que el gen aparece (p.ej. `"TCGA-LGG"`), permitiendo consultas gene-céntricas multi-proyecto.

La colección HGNC actúa así como **puente ontológico** entre las entidades génicas de GDC y las proteínas de UniProt, manteniendo la trazabilidad de identificadores.

---

### 4. UniProtKB

#### 4.1. Naturaleza de la base de datos

UniProtKB es la principal base de datos abierta de secuencias y anotación funcional de proteínas, que integra información de múltiples fuentes experimentales y computacionales.([UniProt][3])

La API REST de UniProt permite recuperar, vía endpoint `uniprotkb/search`, subconjuntos de entradas especificando una consulta (`query`) y un conjunto de campos de salida (`fields`) en formatos como TSV o JSON.([UniProt][9])

#### 4.2. Objetivo en este proyecto

El módulo UniProt tiene dos objetivos principales:

1. Convertir los genes HGNC con `uniprot_ids` en una **lista de proteínas** relevantes para el proyecto TCGA-LGG.
2. Recuperar para esas proteínas un **conjunto acotado de anotaciones** suficientes para análisis biológicos de alto nivel (sin llegar a descargar secuencias completas ni todos los comentarios).

Para ello:

* Se extraen hasta **2000 accesos UniProt únicos** asociados a genes del proyecto (`max_accessions = 2000`).
* Se consultan en lotes la API REST de UniProt restringiendo a:

  * `organism_id:9606` (Homo sapiens).
  * `reviewed:true` (entradas Swiss-Prot con anotación manual).([UniProt][10])

#### 4.3. Ficheros de salida del módulo UniProt

Se generan dos ficheros clave:

1. **`uniprot_mapping_tcga_lgg.tsv`**

   * 2004 filas, 4 columnas:

     * `ensembl_gene_id`: ID Ensembl (sin versión) del gen en el proyecto.
     * `hgnc_id`: identificador HGNC correspondiente.
     * `symbol`: símbolo génico.
     * `uniprot_id`: acceso UniProtKB (p.ej. `P04637`).
   * Este fichero constituye un **mapa gene ↔ proteína**, permitiendo enlazar documentos de GDC/HGNC con proteínas específicas.

2. **`uniprot_metadata_tcga_lgg.tsv`**

   * 2000 filas (una por proteína anotada), 14 columnas.
   * Columnas (según los campos solicitados a la API):([UniProt][9])

     * Identificación básica:

       * `Entry` (accession UniProtKB).
       * `Entry Name` (nombre de la entrada).
       * `Reviewed` (Swiss-Prot vs TrEMBL).
     * Gen y organismo:

       * `Gene Names (primary)` y `Gene Names` (lista de símbolos).
       * `Organism (ID)` (taxID, aquí 9606).
     * Proteína:

       * `Protein names` (nombre recomendado y sinónimos).
       * `Length` (número de aminoácidos).
       * `Protein existence` (evidencia de existencia proteica).
     * Anotación funcional:

       * `Gene Ontology (molecular function)` (`go_f`).
       * `Gene Ontology (biological process)` (`go_p`).
       * `Gene Ontology (cellular component)` (`go_c`).
       * `Subcellular location [CC]` (`cc_subcellular_location`).
       * `Function [CC]` (`cc_function`).

Con estos campos se obtienen datos suficientes para caracterizar la función molecular, procesos biológicos implicados y localización subcelular de las proteínas derivadas de los genes cuantificados.

#### 4.4. Niveles de agregación previstos para la colección UniProt

La colección proteica en MongoDB puede estructurarse con la siguiente jerarquía:

1. **Nivel 1 – Proteína (entrada UniProtKB)**

   * Documento raíz con `uniprot_id` (= `Entry`), `entry_name`, `reviewed`, `protein_existence`, `length`, `organism_id`.

2. **Nivel 2 – Gen(es) asociados**

   * Subdocumento `genes` con:

     * `primary_symbol`,
     * `gene_names` (lista de símbolos),
     * referencias cruzadas a `hgnc_id` y `ensembl_gene_id` vía `uniprot_mapping_tcga_lgg.tsv`.

3. **Nivel 3 – Anotación funcional GO**

   * Subdocumento `go` con tres arrays:

     * `molecular_function`,
     * `biological_process`,
     * `cellular_component`,
       cada uno conteniendo términos GO y, opcionalmente, códigos de evidencia.

4. **Nivel 4 – Comentarios curados (Comment [CC])**

   * Subdocumento `comments` con:

     * `function` (texto de `Function [CC]`),
     * `subcellular_location` (lista de localizaciones, p.ej. membrana plasmática, núcleo).

Esta jerarquía facilita consultas proteo-céntricas (p.ej. “todas las proteínas de membrana codificadas por genes altamente expresados en LGG”).

---

### 5. Encadenamiento GDC → HGNC → UniProt y adecuación a los requisitos

El pipeline implementado materializa la siguiente cadena de integración:

$$
\text{GDC (TCGA-LGG)} \xrightarrow{\text{expresión mRNA}}
\text{Ensembl gene IDs} \xrightarrow{\text{HGNC}}
\text{hgnc-id, symbol, uniprot-ids} \xrightarrow{\text{UniProt REST}}
\text{proteínas anotadas}
$$

Concretamente:

1. **GDC** proporciona:

   * 534 ficheros de expresión **STAR-Counts** para TCGA-LGG.
   * 60 660 genes Ensembl cuantificados, almacenados en `gdc_genes_tcga_lgg.tsv`.
   * Estructura jerárquica **proyecto → caso → fichero → gen** basada en manifest y metadatos.([docs.gdc.cancer.gov][5])

2. **HGNC** actúa como **capa de estandarización génica**:

   * El fichero `hgnc_complete_set.tsv` vincula cada `ensembl_gene_id` a un `hgnc_id`, un `symbol` y, cuando procede, a uno o más `uniprot_ids`.([genenames.org][8])
   * De ahí se extraen 2004 mapeos gen–proteína para genes protein-coding presentes en el proyecto.

3. **UniProt** aporta la **capa proteómica funcional**:

   * 2000 entradas UniProtKB con anotación revisada para proteínas humanas codificadas por esos genes.([UniProt][3])

En términos de la práctica de la asignatura:

* Hay **≥ 3 colecciones interconectadas**:

  * Colección GDC (proyectos/casos/expresión).
  * Colección HGNC (genes y mapeos a bases externas).
  * Colección UniProt (proteínas y anotación funcional).
* Cada colección se ha diseñado con **≥ 3 niveles de anidamiento**:

  * GDC: proyecto → caso → fichero/muestra → resumen génico.
  * HGNC: gen → identificadores/sinónimos → enlaces externos → proyectos.
  * UniProt: proteína → genes → GO/función → sublocalización.
* La **población de datos** es suficiente para análisis de interés:

  * 534 ficheros de expresión, 60 660 genes, 44 618 genes HGNC totales y 2000 proteínas anotadas.
* Los datos están **estrechamente vinculados a bioinformática oncológica** (gliomas TCGA-LGG, genes humanos GRCh38, proteínas humanas anotadas en UniProtKB).

Este andamiaje de datos prepara el terreno para análisis posteriores en MongoDB, tanto gene-céntricos (expresión de genes clave de glioma) como protein-céntricos (identificación de proteínas de membrana, vías funcionales implicadas, etc.), manteniendo una trazabilidad completa desde el nivel de lectura de RNA-seq hasta la anotación proteica curada.

[1]: https://www.ga4gh.org/driver_project/national-cancer-institute-genomic-data-commons-nci-gdc/?utm_source=chatgpt.com "National Cancer Institute Genomic Data Commons (NCI ..."
[2]: https://www.genenames.org/?utm_source=chatgpt.com "HUGO Gene Nomenclature Committee (HGNC)"
[3]: https://www.uniprot.org/help/api_queries?utm_source=chatgpt.com "Programmatic access - Retrieving entries via queries"
[4]: https://portal.gdc.cancer.gov/projects/TCGA-LGG?utm_source=chatgpt.com "TCGA-LGG - GDC Data Portal"
[5]: https://docs.gdc.cancer.gov/Data/Bioinformatics_Pipelines/Expression_mRNA_Pipeline/?utm_source=chatgpt.com "Bioinformatics Pipeline: mRNA Analysis - GDC Docs"
[6]: https://bioconductor.github.io/GenomicDataCommons/?utm_source=chatgpt.com "NIH / NCI Genomic Data Commons Access"
[7]: https://www.nature.com/articles/s41467-021-21254-9?utm_source=chatgpt.com "Uniform genomic data analysis in the NCI ..."
[8]: https://www.genenames.org/download/archive/?utm_source=chatgpt.com "HGNC data archive help"
[9]: https://www.uniprot.org/help/return_fields?utm_source=chatgpt.com "UniProtKB return fields"
[10]: https://www.uniprot.org/help/query-fields?utm_source=chatgpt.com "UniProtKB query fields"
