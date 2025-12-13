# Complete mapping table

This table is “complete” for the **migrated subset** (the part you will actually query). Everything not listed is intentionally excluded for student interpretability, but can be added later as extra data properties without changing the core pattern.

| MongoDB Path                                           | OWL Element Type                  | OWL IRI                               | Domain                      | Range                        | Cardinality | Notes                                                   |
| ------------------------------------------------------ | --------------------------------- | ------------------------------------- | --------------------------- | ---------------------------- | ----------- | ------------------------------------------------------- |
| `hgnc_genes.hgnc_id`                                   | DatatypeProperty                  | `bio:hgncId`                          | `bio:Gene`                  | `xsd:string`                 | exactly 1   | HGNC stable identifier                                  |
| `hgnc_genes.symbol`                                    | DatatypeProperty                  | `bio:geneSymbol`                      | `bio:Gene`                  | `xsd:string`                 | exactly 1   | HGNC gene symbol                                        |
| `hgnc_genes.name`                                      | DatatypeProperty                  | `bio:geneName`                        | `bio:Gene`                  | `xsd:string`                 | 0..1        | Optional human-readable name                            |
| `hgnc_genes.ensembl_gene_id`                           | DatatypeProperty                  | `bio:ensemblGeneId`                   | `bio:Gene`                  | `xsd:string`                 | 0..1        | Join key to UniProt gene block                          |
| `hgnc_genes.locus_group`                               | DatatypeProperty                  | `bio:locusGroup`                      | `bio:Gene`                  | `xsd:string`                 | 0..1        | Kept because it’s interpretable and useful for filters  |
| `hgnc_genes.uniprot_ids[]`                             | ObjectProperty                    | `bio:hasProteinProduct`               | `bio:Gene`                  | `bio:Protein`                | 0..*        | One-to-many HGNC→UniProt                                |
| `uniprot_entries._id`                                  | DatatypeProperty                  | `bio:uniprotId`                       | `bio:Protein`               | `xsd:string`                 | exactly 1   | Primary key of UniProt entry                            |
| `uniprot_entries.organism.taxonomy_id`                 | DatatypeProperty                  | `bio:taxonomyId`                      | `bio:Organism`              | `xsd:integer`                | exactly 1   | NCBI taxon                                              |
| `uniprot_entries.organism.name / scientific_name`      | DatatypeProperty                  | `bio:scientificName`                  | `bio:Organism`              | `xsd:string`                 | 0..1        | Store as literal for display                            |
| `uniprot_entries.organism`                             | ObjectProperty                    | `bio:hasOrganism`                     | `bio:Protein`               | `bio:Organism`               | exactly 1   | Normalizes the organism block                           |
| `uniprot_entries.protein.names[]`                      | DatatypeProperty                  | `bio:proteinName`                     | `bio:Protein`               | `xsd:string`                 | 1..*        | Keep multi-valued (synonyms)                            |
| `uniprot_entries.protein.length`                       | DatatypeProperty                  | `bio:sequenceLength`                  | `bio:Protein`               | `xsd:integer`                | 0..1        | Useful for QC/filters                                   |
| `uniprot_entries.protein.function_cc`                  | DatatypeProperty                  | `bio:functionText`                    | `bio:Protein`               | `xsd:string`                 | 0..1        | Optional; keep truncated text only                      |
| `uniprot_entries.go_terms.molecular_function[]`        | ObjectProperty                    | `bio:hasMolecularFunction`            | `bio:Protein`               | `bio:GOTerm`                 | 0..*        | GO MF linking                                           |
| `uniprot_entries.go_terms.biological_process[]`        | ObjectProperty                    | `bio:hasBiologicalProcess`            | `bio:Protein`               | `bio:GOTerm`                 | 0..*        | GO BP linking                                           |
| `uniprot_entries.go_terms.cellular_component[]`        | ObjectProperty                    | `bio:hasCellularComponent`            | `bio:Protein`               | `bio:GOTerm`                 | 0..*        | GO CC linking                                           |
| `uniprot_entries.gene.hgnc_ids[]`                      | ObjectProperty                    | `bio:proteinProductOf`                | `bio:Protein`               | `bio:Gene`                   | 0..1        | Many-to-one UniProt→HGNC                                |
| `uniprot_entries.gene.ensembl_gene_ids[]`              | DatatypeProperty                  | (reuse) `bio:ensemblGeneId`           | `bio:Gene`                  | `xsd:string`                 | 0..1        | Alternative join route                                  |
| `gdc_cases.case_id`                                    | DatatypeProperty                  | `bio:caseId`                          | `bio:Case`                  | `xsd:string`                 | exactly 1   | UUID-like key                                           |
| `gdc_cases.project_id`                                 | DatatypeProperty / ObjectProperty | `bio:projectId` + `bio:caseInProject` | `bio:Project` / `bio:Case`  | `xsd:string` / `bio:Project` | exactly 1   | Case belongs to one project                             |
| `gdc_cases.disease_type`                               | DatatypeProperty                  | `bio:diseaseTypeLabel`                | `bio:Case`                  | `xsd:string`                 | 0..1        | Can be aligned to NCIt later                            |
| `gdc_cases.primary_site`                               | DatatypeProperty                  | `bio:primarySiteLabel`                | `bio:Case`                  | `xsd:string`                 | 0..1        | Can be aligned to UBERON later                          |
| `hgnc_genes.projects.{PROJECT_ID}`                     | Individual pattern                | `bio:Project` individual              | `bio:Project`               | —                            | 1 per key   | Use `{PROJECT_ID}` as `bio:projectId`                   |
| `hgnc_genes.projects.{PROJECT_ID}.cases.{CASE_ID}`     | Object linkage                    | `bio:hasCase`                         | `bio:Project`               | `bio:Case`                   | 0..*        | Nested join to `gdc_cases.case_id`                      |
| `hgnc_genes.projects.{P}.cases.{C}.file_id`            | DatatypeProperty                  | `bio:fileId`                          | `bio:ExpressionMeasurement` | `xsd:string`                 | 0..1        | File UUID                                               |
| `hgnc_genes.projects.{P}.cases.{C}.unstranded`         | DatatypeProperty                  | `bio:unstrandedCount`                 | `bio:ExpressionMeasurement` | `xsd:decimal`                | 0..1        | Raw count/abundance                                     |
| `hgnc_genes.projects.{P}.cases.{C}.stranded_first`     | DatatypeProperty                  | `bio:strandedFirstCount`              | `bio:ExpressionMeasurement` | `xsd:decimal`                | 0..1        | Strand metric                                           |
| `hgnc_genes.projects.{P}.cases.{C}.stranded_second`    | DatatypeProperty                  | `bio:strandedSecondCount`             | `bio:ExpressionMeasurement` | `xsd:decimal`                | 0..1        | Strand metric                                           |
| `hgnc_genes.projects.{P}.cases.{C}.tpm_unstranded`     | DatatypeProperty                  | `bio:tpmUnstranded`                   | `bio:ExpressionMeasurement` | `xsd:decimal`                | 0..1        | TPM (query-friendly)                                    |
| `hgnc_genes.projects.{P}.cases.{C}.fpkm_unstranded`    | DatatypeProperty                  | `bio:fpkmUnstranded`                  | `bio:ExpressionMeasurement` | `xsd:decimal`                | 0..1        | FPKM                                                    |
| `hgnc_genes.projects.{P}.cases.{C}.fpkm_uq_unstranded` | DatatypeProperty                  | `bio:fpkmUqUnstranded`                | `bio:ExpressionMeasurement` | `xsd:decimal`                | 0..1        | FPKM-UQ                                                 |

---




[1]: https://obofoundry.org/id-policy.html?utm_source=chatgpt.com "OBO Foundry Identifier Policy"
[2]: https://obofoundry.org/ontology/go.html?utm_source=chatgpt.com "Gene ontology"
[3]: https://purl.obolibrary.org/obo/ncit/releases/2024-05-07/ncit.owl?utm_source=chatgpt.com "http://purl.obolibrary.org/obo/ncit/releases/2024-..."
[4]: https://obofoundry.org/ontology/uberon.html?utm_source=chatgpt.com "Uberon multi-species anatomy ontology"
[5]: https://obofoundry.org/ontology/ncit.html?utm_source=chatgpt.com "NCI Thesaurus OBO Edition"
[6]: https://obofoundry.org/ontology/obi.html?utm_source=chatgpt.com "OBI (Ontology for Biomedical Investigations)"
[7]: https://www.uniprot.org/help/rdf?utm_source=chatgpt.com "rdf in UniProt help search"
[8]: https://www.genenames.org/data/gene-symbol-report/?utm_source=chatgpt.com "Symbol report for A1BG"
[9]: https://docs.cancergenomicscloud.org/docs/tcga-metadata?utm_source=chatgpt.com "TCGA metadata - The CGC Knowledge Center"
