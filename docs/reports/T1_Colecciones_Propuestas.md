# Colecciones Propuestas para la tarea T1

## Propósito y criterios de búsqueda

**Propósito.** Localizar colecciones biomédicas abiertas que permitan poblar una BD MongoDB para T1 con ≥3 colecciones interconectadas y ≥3 niveles de anidamiento por colección, datos realistas y volumen suficiente; además, que faciliten las futuras consultas de T2 y la modelización ontológica de T3.  

**Criterios de búsqueda principales.**

* Dominio: genómica del cáncer, imagen médica oncológica, farmacogenómica.
* Acceso: descargas o APIs abiertas en JSON/TSV/GraphQL.
* Estructura: jerarquías claras (p. ej., proyecto→caso→muestra; paciente→estudio→serie→instancia).
* Interoperabilidad: identificadores estables (HGNC/Ensembl/UniProt, TCGA barcodes, ChEMBL IDs) y alineables entre colecciones.
* Tamaño: suficiente para consultas analíticas y SPARQL en T3.

**Validación:** Criterios alineados con T1 y con las dependencias a T2–T3. Continuar. 

---

## Conjuntos de Colecciones Propuestos

### Conjunto A — Oncogenómica TCGA + Normalización génica-proteica (GDC + HGNC + UniProtKB)

**Resumen científico.** Este conjunto integra datos clínico–moleculares de TCGA desde el NCI Genomic Data Commons (GDC), mapeados a símbolos génicos aprobados por HGNC y a proteínas anotadas en UniProtKB. TCGA molecularizó >20 000 muestras en 33 tipos tumorales y caracterizó >11 000 casos; GDC expone entidad–relaciones (proyecto→caso→muestra→aliquot/archivos) y API para descarga. HGNC provee nomenclatura génica humana (~42 000 símbolos); UniProtKB aporta proteómica de referencia y metadatos descargables. Esto crea un grafo natural caso↔muestra↔gen↔proteína para consultas analíticas y posterior ontologización. ([Cancer.gov][1])

| Colección                                   | Niveles de Agregación                                                      | Relaciones de esta colección con el resto                                                                         | Tamaño muestral (aproximado)                                                         | Formato/Acceso                            |                      |
| ------------------------------------------- | -------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ | ----------------------------------------- | -------------------- |
| **GDC/TCGA (clínico, biospecimen, ómicos)** | Programa/Proyecto → Caso → Muestra → Porción/Alícuota → Archivos           | Casos TCGA enlazables a imágenes TCIA por barcode; variantes/expresión mapeables a genes HGNC y proteínas UniProt | TCGA global: >11 000 casos y >20 000 muestras; p.ej., COAD 461 casos; HNSC 528 casos | Portal y API JSON/TSV; Data Transfer Tool | ([Cancer.gov][1])    |
| **HGNC (símbolos génicos)**                 | Base → Símbolo aprobado → Mapeos (Ensembl, NCBI, UniProt)                  | Normaliza genes de TCGA; puente hacia UniProt y otras fuentes                                                     | ~42 000 símbolos aprobados                                                           | Descargas TSV/JSON periódicas             | ([genenames.org][2]) |
| **UniProtKB (proteínas humanas)**           | Conjunto → Entrada revisada (Swiss-Prot) → Isoformas/Features → Cross-refs | Mapea proteínas a genes HGNC; añade funciones y dominios para T3                                                  | 573 661 entradas revisadas; 199 M no revisadas (2025_04)                             | Descargas y API; TSV/FASTA/JSON           | ([UniProt][3])       |

**Relaciones clave y beneficios T2–T3.**

* Claves: `case_id`/`submitter_id` (TCGA), `HGNC_ID`/símbolo HGNC, `UniProt Accession`.
* Queries T2: “mutaciones en TP53 por proyecto y estadio”, “supervivencia por firma de expresión”, “enriquecimiento GO por conjunto de genes”.
* T3: clases `Paciente`, `Muestra`, `Gen`, `Proteína`, propiedades `expresa`, `altera`, `codifica`. Los identificadores estables simplifican IRIs y razonado. 

**Validación:** Cumple ≥3 colecciones y ≥3 niveles de agregación; acceso abierto y tratable en Python vía API/TSV. Continuar.

---

### Conjunto B — Radiogenómica TCGA Glioma: Imágenes TCIA + Segmentaciones/Features + Clínica/Moléculas GDC

**Resumen científico.** Las colecciones TCGA-GBM y TCGA-LGG en TCIA aportan imágenes DICOM organizadas jerárquicamente (Colección→Paciente→Estudio→Serie→Instancia). Están explícitamente enlazadas con los datos clínicos y genómicos de los mismos sujetos en GDC. El dataset de Bakas et al. añade segmentaciones expertas y *radiomic features* para 243 casos preoperatorios, permitiendo integrar fenotipos de imagen con genómica clínica. Esta tripleta habilita escenarios radiogenómicos reproducibles y consultas multimodales. ([The Cancer Imaging Archive (TCIA)][4])

| Colección                                           | Niveles de Agregación                                    | Relaciones de esta colección con el resto                          | Tamaño muestral (aproximado)                                  | Formato/Acceso                             |                                          |
| --------------------------------------------------- | -------------------------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------- | ------------------------------------------ | ---------------------------------------- |
| **TCIA – TCGA-LGG/GBM (imágenes)**                  | Colección → Paciente → Estudio → Serie → Instancia DICOM | Mapeo 1-a-1 a sujetos TCGA en GDC; usa jerarquía DICOM estándar    | LGG: 108; GBM: 135 preoperatorios con segmentaciones (subset) | Descarga vía portal y APIs NBIA            | ([The Cancer Imaging Archive (TCIA)][4]) |
| **Segmentaciones/Features (Bakas 2017)**            | Paciente → Imagen multimodal → Etiquetas → Features      | Referencia a pacientes TCGA-LGG/GBM de TCIA                        | 243 estudios con máscaras y *features*                        | Descargas asociadas al artículo/datos TCIA | ([Nature][5])                            |
| **GDC/TCGA (clínico/ómicos de los mismos sujetos)** | Proyecto → Caso → Muestra → Archivos                     | Unificación por TCGA barcode del sujeto; enlaza clínica y mutómica | Véase TCGA global; proyectos LGG/GBM dentro de GDC            | Portal y API JSON/TSV                      | ([docs.gdc.cancer.gov][6])               |

**Notas técnicas.**

* La jerarquía DICOM y los filtros por Paciente/Estudio/Serie están estandarizados; NBIA REST API devuelve metadatos a nivel de serie, combinando paciente/estudio/serie para automatizar descargas. ([wiki.cancerimagingarchive.net][7])
* TCIA declara explícitamente el *linkage* con GDC para las colecciones TCGA. ([The Cancer Imaging Archive (TCIA)][8])

**Beneficios T2–T3.**

* T2: consultas que cruzan *features* radiómicas con clínica y mutaciones; exportables a XML→XSLT.
* T3: clases `Imagen`, `Serie`, `Segmentación`, `RadiomicFeature`, `Gen`; propiedades `derivaDe`, `anota`, `asociadaCon`. Razonadores sobre tipos de imagen y regiones.

**Validación:** Cumple interconexión y ≥3 niveles por colección; formatos y APIs públicos. Continuar.

---

### Conjunto C — Farmacogenómica traslacional (Open Targets Platform + ChEMBL + HGNC/DisGeNET)

**Resumen científico.** Open Targets Platform integra evidencias multi-fuente para asociaciones *target–disease* y ofrece descargas y GraphQL. ChEMBL 36 aporta compuestos, dianas y actividades bioensayo; HGNC estabiliza la nomenclatura génica para cruzar IDs. DisGeNET (opcional) ofrece GDAs a gran escala. Este conjunto habilita consultas de *drug-target-disease* con alineación génica robusta. ([platform.opentargets.org][9])

| Colección                 | Niveles de Agregación                                     | Relaciones de esta colección con el resto                                 | Tamaño muestral (aproximado)                                          | Formato/Acceso                  |                                       |
| ------------------------- | --------------------------------------------------------- | ------------------------------------------------------------------------- | --------------------------------------------------------------------- | ------------------------------- | ------------------------------------- |
| **Open Targets Platform** | Enfermedad ↔ Target → Evidencias (fuente/tipo/puntuación) | Usa IDs Ensembl/HGNC y enlaza a ChEMBL para fármacos                      | Plataforma con asociaciones y evidencias actualizadas trimestralmente | Descargas TSV/JSON; GraphQL API | ([platform-docs.opentargets.org][10]) |
| **ChEMBL 36**             | Molécula → Ensayo → Actividad → Dianas                    | Targets enlazables a UniProt/HGNC; fármacos enlazables desde Open Targets | ~2,8 M compuestos; 17 803 dianas                                      | Descargas y web services        | ([EMBL-EBI][11])                      |
| **HGNC**                  | Base → Símbolo → Mapeos                                   | Normaliza genes presentes en Open Targets/ChEMBL/DisGeNET                 | ~42 000 símbolos                                                      | TSV/JSON periódicos             | ([genenames.org][12])                 |
| **(Opcional) DisGeNET**   | Gen ↔ Enfermedad → Evidencias/Fuentes                     | GDAs paralelas para validación y cobertura                                | 2,02 M GDAs (v25.3)                                                   | Descargas con registro          | ([disgenet.org][13])                  |

**Relaciones clave y beneficios T2–T3.**

* Claves: `Ensembl Gene ID`/símbolo HGNC, `UniProt Accession`, `ChEMBL_ID`.
* T2: top-N *targets* por enfermedad con evidencia ≥ umbral; moléculas activas por target y su actividad cuantitativa.
* T3: clases `Target`, `Disease`, `Drug`, propiedades `implicadoEn`, `moduladoPor`, con axiomas de consistencia entre fuentes.

**Validación:** Cumple ≥3 colecciones y ≥3 niveles; Open Targets/ChEMBL ofrecen descargas/GraphQL; DisGeNET requiere registro pero es accesible. Continuar.

---

## Consideraciones de modelado para T1

* **Normalización y claves.** Adoptar HGNC como *authority* para `gene_id`; unificar `case_id` TCGA y `patient_id` TCIA vía barcode; `chembl_id` y `uniprot_acc` para *targets*. Documentar decisiones de normalización/denormalización y plan de índices (p. ej., `{case_id, gene_id}`, `{target_id, disease_id}`). 
* **Anidamiento sugerido (MongoDB).**

  * GDC/TCGA: `project{cases[ samples[ aliquots[] ] ], files[] }`.
  * TCIA: `collection{patients[ studies[ series[ instances[] ] ] ]}`.
  * ChEMBL/OpenTargets: `target{ associations[ evidence[] ] }`, `molecule{ activities[] }`.
* **Alineación con T2–T3.** Las estructuras propuestas soportan pipelines JSON→XML→XSLT y mapeo a OWL con IRIs estables. 

**Validación:** El diseño respeta los requisitos de anidamiento y relaciones de T1 y prepara entradas parametrizables para T2. Continuar. 

---

## Notas y limitaciones

* **Tamaños muestrales.** Algunos conteos son aproximados o por proyecto; TCGA total y ejemplos por proyecto están referenciados. ([Cancer.gov][1])
* **Acceso DisGeNET.** Descargas amplias requieren registro y plan; si no se acepta, se puede suplir con Open Targets + ChEMBL + HGNC. ([disgenet.org][14])
* **Integración TCIA↔GDC.** Requiere atención al *barcode* TCGA y a la jerarquía DICOM en NBIA al programar descargas masivas. ([wiki.cancerimagingarchive.net][15])

**Validación:** Las limitaciones no impiden cumplir T1; quedan documentadas alternativas y trazabilidad. Continuar.

---

## Referencias

* Aerts, H. J. W. L., et al. (2014). Decoding tumour phenotype by noninvasive imaging using a quantitative radiomics approach. *Nature Communications*, 5, 4006. [https://doi.org/10.1038/ncomms5006](https://doi.org/10.1038/ncomms5006)  y recurso PMC. ([PMC][16])
* Bakas, S., et al. (2017). Advancing The Cancer Genome Atlas glioma MRI collections with expert segmentation labels and radiomic features. *Scientific Data*, 4, 170117. [https://doi.org/10.1038/sdata2017117](https://doi.org/10.1038/sdata2017117) ([Nature][5])
* EMBL-EBI. (2025, Oct 15). *ChEMBL 36 is live*. [https://www.ebi.ac.uk/about/news/updates-from-data-resources/chembl-36/](https://www.ebi.ac.uk/about/news/updates-from-data-resources/chembl-36/) ([EMBL-EBI][11])
* Genenames.org. (2025). *Statistics & download files (HGNC)*. [https://www.genenames.org/download/statistics-and-files/](https://www.genenames.org/download/statistics-and-files/) ([genenames.org][12])
* NCI. (s. f.). *The Cancer Genome Atlas (TCGA)*. [https://www.cancer.gov/ccg/research/genome-sequencing/tcga](https://www.cancer.gov/ccg/research/genome-sequencing/tcga) ([Cancer.gov][1])
* NCI GDC. (s. f.). *GDC Data Model*. [https://gdc.cancer.gov/developers/gdc-data-model](https://gdc.cancer.gov/developers/gdc-data-model)  y *API Users Guide*. [https://docs.gdc.cancer.gov/API/Users_Guide/Search_and_Retrieval/](https://docs.gdc.cancer.gov/API/Users_Guide/Search_and_Retrieval/) ([NCI Genomic Data Commons][17])
* NCI GDC Portal. (s. f.). *Projects: TCGA-COAD; TCGA-HNSC*. [https://portal.gdc.cancer.gov/projects/TCGA-COAD](https://portal.gdc.cancer.gov/projects/TCGA-COAD) ; [https://portal.gdc.cancer.gov/projects/TCGA-HNSC](https://portal.gdc.cancer.gov/projects/TCGA-HNSC) ([GDC Portal][18])
* NCI GDC Portal. (s. f.). *Repository Tool (totales GDC)*. [https://portal.gdc.cancer.gov/analysis_page?app=Downloads](https://portal.gdc.cancer.gov/analysis_page?app=Downloads) ([GDC Portal][19])
* The Cancer Imaging Archive (TCIA). (s. f.). *TCGA Collections (BRCA/LGG/GBM) – enlace con GDC*. [https://www.cancerimagingarchive.net/collection/tcga-brca/](https://www.cancerimagingarchive.net/collection/tcga-brca/) ; [https://www.cancerimagingarchive.net/collection/tcga-lgg/](https://www.cancerimagingarchive.net/collection/tcga-lgg/) ([The Cancer Imaging Archive (TCIA)][8])
* TCIA Wiki. (2014–2021). *NBIA REST API Guides* y *Radiology Portal User’s Guide*. [https://wiki.cancerimagingarchive.net/display/Public/NBIA%2BSearch%2BREST%2BAPI%2BGuide](https://wiki.cancerimagingarchive.net/display/Public/NBIA%2BSearch%2BREST%2BAPI%2BGuide) ; [https://wiki.cancerimagingarchive.net/display/NBIA](https://wiki.cancerimagingarchive.net/display/NBIA) ([wiki.cancerimagingarchive.net][15])
* UniProt Consortium. (2025). *UniProtKB—Statistics & Release 2025_04*. [https://www.uniprot.org/uniprotkb](https://www.uniprot.org/uniprotkb) ; [https://www.uniprot.org/uniprotkb/statistics](https://www.uniprot.org/uniprotkb/statistics) ; [https://www.uniprot.org/release-notes/2025-10-15-release](https://www.uniprot.org/release-notes/2025-10-15-release) ([UniProt][3])
* Open Targets. (2025). *Platform downloads and data access*. [https://platform.opentargets.org/downloads](https://platform.opentargets.org/downloads) ; [https://platform-docs.opentargets.org/data-access](https://platform-docs.opentargets.org/data-access) ; [https://platform-docs.opentargets.org/associations](https://platform-docs.opentargets.org/associations) ([platform.opentargets.org][9])
* Piñero, J., et al. (2025). *DISGENET v25.3 – Database Information & Statistics*. [https://www.disgenet.org/dbinfo](https://www.disgenet.org/dbinfo) ([disgenet.org][13])
* DICOM Standard Committee. (s. f.). *Service Class Specifications* y jerarquía Patient/Study/Series/Instance. [https://www.dicomstandard.org/standards/view/service-class-specifications](https://www.dicomstandard.org/standards/view/service-class-specifications) ([DICOM][20])

---

## Apéndice — Contexto T1 del proyecto

T1 requiere: MongoDB, ≥3 colecciones interconectadas, ≥3 niveles de anidamiento por colección, población suficiente y datos realistas; además, documentar relaciones, normalización y plan de índices. Depende hacia T2 y T3.  

**Validación final:** Cada conjunto propuesto incluye ≥3 colecciones y ≥3 niveles de agregación, formatos abiertos adecuados para Python, y relaciones explícitas entre colecciones. Se documentaron accesos y límites menores. Continuar con selección e instanciación en MongoDB.

[1]: https://www.cancer.gov/ccg/research/genome-sequencing/tcga "The Cancer Genome Atlas Program (TCGA) - NCI"
[2]: https://www.genenames.org/ "HUGO Gene Nomenclature Committee: Home"
[3]: https://www.uniprot.org/uniprotkb "UniProt Knowledgebase (UniProtKB)"
[4]: https://www.cancerimagingarchive.net/collection/tcga-lgg/ "TCGA-LGG - The Cancer Imaging Archive (TCIA)"
[5]: https://www.nature.com/articles/sdata2017117 "Advancing The Cancer Genome Atlas glioma MRI ..."
[6]: https://docs.gdc.cancer.gov/Data/Data_Model/GDC_Data_Model/ "GDC Data Model - GDC Docs - National Cancer Institute"
[7]: https://wiki.cancerimagingarchive.net/display/NBIA "TCIA Radiology Portal User's Guide"
[8]: https://www.cancerimagingarchive.net/collection/tcga-brca/ "TCGA-BRCA - The Cancer Imaging Archive (TCIA)"
[9]: https://platform.opentargets.org/downloads "Data downloads | Open Targets Platform"
[10]: https://platform-docs.opentargets.org/ "Open Targets Platform"
[11]: https://www.ebi.ac.uk/about/news/updates-from-data-resources/chembl-36/ "ChEMBL 36 is live"
[12]: https://www.genenames.org/download/ "HGNC download files overview"
[13]: https://www.disgenet.org/dbinfo "DISGENET: Database Information"
[14]: https://www.disgenet.org/downloads "FIND YOUR PERFECT PLAN"
[15]: https://wiki.cancerimagingarchive.net/display/Public/NBIA%2BSearch%2BREST%2BAPI%2BGuide "NBIA Search REST API Guide"
[16]: https://pmc.ncbi.nlm.nih.gov/articles/PMC4059926/ "Decoding tumour phenotype by noninvasive imaging using ..."
[17]: https://gdc.cancer.gov/developers/gdc-data-model "GDC Data Model - NCI Genomic Data Commons"
[18]: https://portal.gdc.cancer.gov/projects/TCGA-COAD "TCGA-COAD - GDC Data Portal"
[19]: https://portal.gdc.cancer.gov/analysis_page?app=Downloads&utm_source=chatgpt.com "Repository Tool - GDC Data Portal - National Cancer Institute"
[20]: https://www.dicomstandard.org/standards/view/service-class-specifications "4 Service Class Specifications - DICOM"
