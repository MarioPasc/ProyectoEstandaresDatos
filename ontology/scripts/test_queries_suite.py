import rdflib
from pathlib import Path

# Configuración de rutas
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
# Asegúrate de que el nombre del archivo coincida con el que generaste
TTL_FILE = ROOT_DIR / "data" / "rdf" / "biointegrate_data_overlay.ttl" 

def run_test_suite():
    if not TTL_FILE.exists():
        print(f"❌ Archivo no encontrado: {TTL_FILE}")
        return

    print(f"--- Cargando Grafo ({TTL_FILE.name}) ---")
    g = rdflib.Graph()
    g.parse(str(TTL_FILE), format="turtle")
    print(f"✓ Grafo cargado con {len(g)} tripletas.\n")

    queries = {
        "Q2 (Filtro Proyecto/Casos)": """
            PREFIX bi: <http://example.org/biointegrate/>
            SELECT ?projectId ?caseId WHERE {
              ?case a bi:Case ;
                    bi:caseId ?caseId ;
                    bi:caseInProject ?project .
              ?project bi:projectId ?projectId .
              FILTER(?projectId = "TCGA-GBM")
            } LIMIT 5
        """,
        "Q3 (Métricas > 1000)": """
            PREFIX bi: <http://example.org/biointegrate/>
            SELECT ?caseId ?geneSymbol ?count WHERE {
              ?meas a bi:ExpressionMeasurement ;
                    bi:unstrandedCount ?count ;
                    bi:measuredCase ?case ;
                    bi:measuredGene ?gene .
              ?case bi:caseId ?caseId .
              ?gene bi:geneSymbol ?geneSymbol .
              FILTER(?count > 1000)
            } ORDER BY DESC(?count) LIMIT 5
        """,
        "Q4 (Búsqueda 'remodeling')": """
            PREFIX bi: <http://example.org/biointegrate/>
            SELECT ?uniprotId ?proteinName WHERE {
                ?protein a bi:Protein ;
                    bi:uniprotId ?uniprotId ;
                    bi:proteinName ?proteinName .
            FILTER(regex(str(?proteinName), "remodeling", "i"))
            } LIMIT 5
        """,
        "Q5 (Join Semántico G-P-C)": """
            PREFIX bi: <http://example.org/biointegrate/>
            SELECT DISTINCT ?caseId ?geneSymbol ?uniprotId WHERE {
              ?meas a bi:ExpressionMeasurement ;
                    bi:measuredCase ?case ;
                    bi:measuredGene ?gene .
              ?case bi:caseId ?caseId .
              ?gene bi:geneSymbol ?geneSymbol ;
                    bi:hasProteinProduct ?protein .
              ?protein bi:uniprotId ?uniprotId .
            } LIMIT 5
        """,
        "Q6 (BioEntity Inferences)": """
            PREFIX bi: <http://example.org/biointegrate/>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            SELECT ?clase_especifica (COUNT(?entidad) AS ?total) WHERE {
              ?entidad rdf:type bi:BioEntity .
              ?entidad rdf:type ?clase_especifica .
              FILTER(?clase_especifica != bi:BioEntity)
              FILTER(?clase_especifica != <http://www.w3.org/2002/07/owl#NamedIndividual>)
            } GROUP BY ?clase_especifica
        """
    }

    for name, q_text in queries.items():
        print(f"Executing {name}...")
        try:
            results = g.query(q_text)
            if len(results) == 0:
                print("   ⚠️  Sin resultados (revisa si los datos existen en Mongo).")
            else:
                for row in results:
                    print(f"   -> {row}")
        except Exception as e:
            print(f"   ❌ Error en la consulta: {e}")
        print("-" * 50)

if __name__ == "__main__":
    run_test_suite()