# Diseño de la Colección: proteins (UniProt)

Este documento describe el esquema de la colección `proteins` en MongoDB, basada en los ficheros `uniprot_metadata...tsv` y `uniprot_mapping...tsv`.


## Instrucciones de Importación (Paso a Paso)

Para poblar esta colección desde cero, se deben seguir los siguientes pasos en el entorno estandares:

### 1. Configuración y Dependencias
Asegurarse de que el fichero config/data_config.yaml tiene las rutas locales configuradas correctamente y que las librerías necesarias están instaladas.

```bash
# Instalar el paquete del proyecto y librerías de DB
pip install -e .
pip install pandas pymongo pyyaml
```
### 2. Descarga de Datos (Dependencias y Source: UniProt)
Descargar primero los datos de GDC (para obtener la lista de genes del proyecto) y luego descargar los datos de UniProt (Metadata y Mapping).

```bash
# 1. Descargar GDC (requisito previo)
datastandards-download --config config/data_config.yaml --source gdc

# 2. Descargar UniProt (genera los ficheros metadata y mapping)
datastandards-download --config config/data_config.yaml --source uniprot
```

### 3. Ejecución del Script de Importación
Ejecutar el script de Python que carga el fichero de mapeo (mapping_output), lee el fichero de metadatos (metadata_output), combina la información y puebla la colección proteins.

```bash
python DataStandards/db/import_proteins_mongo.py
```

## Estructura del Documento

Cada documento utiliza el `Entry` (accession de UniProt) como clave principal (`_id`). La estructura anidada se utiliza para almacenar la información de los genes asociados y las anotaciones GO y de localización.


| Nivel | Campo | Descripción |
|-------|-------|-------------|
| Nivel 1 | _id | Clave principal. El Entry de UniProt (ej. "P04217"). |
| Nivel 1 | entry_name | Nombre de la entrada (ej. "A1BG_HUMAN"). |
| Nivel 1 | protein_names | Nombres recomendados y alternativos de la proteína. |
| Nivel 2 | genes | Array de documentos que lista los genes asociados. |
| Nivel 3 | genes.hgnc_id | ID de HGNC del gen asociado. |
| Nivel 3 | genes.symbol | Símbolo del gen asociado. |
| Nivel 2 | go | Objeto que agrupa las anotaciones de Gene Ontology. |
| Nivel 3 | go.molecular_function | Array de términos de función molecular. |
| Nivel 3 | go.biological_process | Array de términos de proceso biológico. |
| Nivel 3 | go.cellular_component | Array de términos de componente celular. |
| Nivel 2 | comments | Objeto que agrupa comentarios de curación. |
| Nivel 3 | comments.function | Texto de la función de la proteína. |
| Nivel 3 | comments.subcellular_location | Array de localizaciones subcelulares. |

### Ejemplo de Documento (JSON)

```json
{
  "_id": "P04217",
  "entry_name": "A1BG_HUMAN",
  "reviewed": "reviewed",
  "protein_existence": "Evidence at protein level",
  "length": 496,
  "organism_id": 9606,
  "protein_names": "Alpha-1-B glycoprotein (A1BG)",
  "genes": [
    {
      "ensembl_gene_id": "ENSG00000121410",
      "hgnc_id": "HGNC:5",
      "symbol": "A1BG"
    }
  ],
  "go": {
    "molecular_function": [
      "molecular_function (GO:0005576)"
    ],
    "biological_process": [],
    "cellular_component": [
      "extracellular region (GO:0005576)",
      "extracellular space (GO:0005615)"
    ]
  },
  "comments": {
    "function": "Function: The specific function is not known.",
    "subcellular_location": [
      "Secreted"
    ]
  }
}

