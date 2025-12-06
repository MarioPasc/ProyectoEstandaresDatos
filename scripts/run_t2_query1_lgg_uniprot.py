#!/usr/bin/env python
"""
Script de prueba para la consulta T2 - Query 1 (TCGA-LGG + UniProt).

Ejecuta una agregación sobre la colección HGNC y enriquece
con anotaciones de UniProt y metadatos de GDC.
"""

from pymongo import MongoClient
from pprint import pprint

MONGO_URI = "mongodb://localhost:27017"

# Nombre de la base de datos
DB_NAME = "biointegrate"

# Nombres de las colecciones (según cómo se hizo el mongoimport)
HGNC_COLLECTION = "hgnc_collection"
GDC_COLLECTION = "gdc_collection_export"
UNIPROT_COLLECTION = "uniprot_collection_export"

# Número de genes a mostrar (solo para debug)
N_RESULTS = 10

# -------------------------------------------------------------------


def main():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]

    hgnc_col = db[HGNC_COLLECTION]

    # Pipeline de agregación
    pipeline = [
        # 1) Filtrar genes con datos de TCGA-LGG
        {
            "$match": {
                "projects.TCGA-LGG": {"$exists": True}
            }
        },

        # 2) Proyectar campos básicos y convertir el diccionario de cases a array
        {
            "$project": {
                "hgnc_id": 1,
                "symbol": 1,
                "ensembl_gene_id": 1,
                "uniprot_ids": 1,
                "cases_array": {
                    "$objectToArray": "$projects.TCGA-LGG.cases"
                }
            }
        },

        # 3) Unwind: 1 documento por (gen, caso)
        {
            "$unwind": "$cases_array"
        },

        # 4) Agrupar de nuevo por gen y calcular media de TPM y nº de casos
        {
            "$group": {
                "_id": {
                    "hgnc_id": "$hgnc_id",
                    "symbol": "$symbol",
                    "ensembl_gene_id": "$ensembl_gene_id",
                    "uniprot_ids": "$uniprot_ids",
                },
                "mean_tpm_unstranded": {
                    "$avg": "$cases_array.v.tpm_unstranded"
                },
                "n_cases": {"$sum": 1},
            }
        },

        # 5) Volver a sacar los identificadores al nivel superior
        {
            "$project": {
                "_id": 0,
                "hgnc_id": "$_id.hgnc_id",
                "symbol": "$_id.symbol",
                "ensembl_gene_id": "$_id.ensembl_gene_id",
                "uniprot_ids": "$_id.uniprot_ids",
                "mean_tpm_unstranded": 1,
                "n_cases": 1,
            }
        },

        # 6) $lookup a UniProt usando la lista de uniprot_ids
        {
            "$lookup": {
                "from": UNIPROT_COLLECTION,
                "let": {"uniprot_ids": "$uniprot_ids"},
                "pipeline": [
                    {"$unwind": "$uniprot_entries"},
                    {
                        "$match": {
                            "$expr": {
                                "$in": [
                                    "$uniprot_entries.uniprot_id",
                                    {"$ifNull": ["$$uniprot_ids", []]},
                                ]
                            }
                        }
                    },
                    {
                        "$project": {
                            "_id": 0,
                            "uniprot_id": "$uniprot_entries.uniprot_id",
                            "protein_name": {
                                "$arrayElemAt": [
                                    "$uniprot_entries.protein.names",
                                    0,
                                ]
                            },
                            "protein_length": "$uniprot_entries.protein.length",
                            "function_cc": "$uniprot_entries.protein.function_cc",
                            "go_molecular_function": (
                                "$uniprot_entries.go_terms.molecular_function"
                            ),
                        }
                    },
                ],
                "as": "uniprot_annotations",
            }
        },

        # 7) $lookup ligero a GDC para meter disease_type y primary_site de TCGA-LGG
        {
            "$lookup": {
                "from": GDC_COLLECTION,
                "let": {},
                "pipeline": [
                    {"$unwind": "$projects"},
                    {"$match": {"projects.project_id": "TCGA-LGG"}},
                    {
                        "$project": {
                            "_id": 0,
                            "project_id": "$projects.project_id",
                            "disease_type": "$projects.disease_type",
                            "primary_site": "$projects.primary_site",
                        }
                    },
                ],
                "as": "gdc_project",
            }
        },

        # 8) Aplanar el array de GDC (sabemos que habrá solo 1 elemento)
        {
            "$addFields": {
                "project": {"$arrayElemAt": ["$gdc_project", 0]}
            }
        },
        {
            "$project": {
                "gdc_project": 0
            }
        },

        # 9) Ordenar por TPM medio descendente y limitar
        {
            "$sort": {"mean_tpm_unstranded": -1}
        },
        {
            "$limit": 100
        },
    ]

    print("Ejecutando pipeline de agregación sobre HGNC...\n")
    cursor = hgnc_col.aggregate(pipeline)

    print(f"Mostrando los primeros {N_RESULTS} genes:\n")
    for i, doc in enumerate(cursor):
        if i >= N_RESULTS:
            break
        pprint(doc)
        print("-" * 80)


if __name__ == "__main__":
    main()
