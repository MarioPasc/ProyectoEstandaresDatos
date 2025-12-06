# Diseño de la Colección: genes (HGNC)

Este documento describe el esquema de la colección `genes` en MongoDB, basada en el fichero `hgnc_complete_set.tsv`.


## Instrucciones de Importación (Paso a Paso)

Para poblar esta colección desde cero, se deben seguir los siguientes pasos en el entorno estandares:

### 1. Configuración y Dependencias
Asegurarse de que el fichero config/data_config.yaml tiene las rutas locales configuradas correctamente y que las librerías necesarias están instaladas.

```bash
# Instalar el paquete del proyecto y librerías de DB
pip install -e .
pip install pandas pymongo pyyaml
```
### 2. Descarga de Datos (Source: HGNC)
Descargar el fichero hgnc_complete_set.tsv usando la herramienta CLI del proyecto.

```bash
datastandards-download --config config/data_config.yaml --source hgnc
```

### 3. Ejecución del Script de Importación
Ejecutar el script de Python que lee el TSV, transforma los datos al esquema JSON definido arriba e inserta los documentos en MongoDB.
```bash
python DataStandards/db/import_genes_mongo.py
```

## Estructura del Documento

Cada documento en la colección utiliza el `hgnc_id` como clave principal (`_id`). La estructura sigue una jerarquía anidada de 4 niveles para agrupar la información de forma lógica.

| Nivel | Campo | Descripción |
|-------|-------|-------------|
| Nivel 1 | _id | Clave principal. El hgnc_id (ej. "HGNC:5"). |
| Nivel 1 | symbol | Símbolo oficial del gen (ej. "A1BG"). |
| Nivel 1 | name | Nombre completo del gen. |
| Nivel 1 | locus_group | Grupo de locus (ej. "protein-coding gene"). |
| Nivel 2 | identifiers | Objeto que agrupa IDs de otras bases de datos. |
| Nivel 3 | identifiers.ensembl_gene_id | ID de Ensembl. |
| Nivel 3 | identifiers.entrez_id | ID de Entrez. |
| Nivel 2 | synonyms | Objeto que agrupa alias y nombres previos. |
| Nivel 3 | synonyms.alias_symbol | Array de símbolos alternativos. |
| Nivel 3 | synonyms.prev_symbol | Array de símbolos previos. |
| Nivel 2 | external_links | Objeto que agrupa enlaces a bases de datos externas. |
| Nivel 3 | external_links.uniprot_ids | Array de IDs de UniProt. |
| Nivel 3 | external_links.omim_id | Array de IDs de OMIM. |

### Ejemplo de Documento (JSON)

```json
{
  "_id": "HGNC:5",
  "symbol": "A1BG",
  "name": "alpha-1-B glycoprotein",
  "locus_group": "protein-coding gene",
  "locus_type": "gene with protein product",
  "status": "Approved",
  "location": "19q13.43",
  "identifiers": {
    "ensembl_gene_id": "ENSG00000121410",
    "entrez_id": "1",
    "refseq_accession": "NM_130786",
    "ucsc_id": "uc002sfu.2"
  },
  "synonyms": {
    "alias_symbol": ["A1B"],
    "prev_symbol": ["GAB"],
    "alias_name": [],
    "prev_name": []
  },
  "external_links": {
    "uniprot_ids": ["P04217"],
    "omim_id": ["138670"],
    "orphanet": null,
    "cosmic": "A1BG"
  }
}
```

