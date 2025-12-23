import pymongo
from rdflib import Graph, Literal, RDF, URIRef, Namespace
from rdflib.namespace import XSD
from pathlib import Path

# Configuración de Namespaces
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
BI = Namespace("http://example.org/biointegrate/")

def mongo_to_rdf():
    client = pymongo.MongoClient("mongodb://localhost:27017/")
    db = client["estandares_db"]
    g = Graph()
    g.bind("bi", BI)

    print("--- Iniciando Mapeo Semántico (Estructura Real) ---")

    # 1. Proyectos y Casos (gdc_cases)
    # Según image_bba2ee.png: _id es el proyecto, cases es un Array
    for project_doc in db["gdc_cases"].find():
        p_id = project_doc.get("project_id") or project_doc.get("_id")
        project_uri = URIRef(BI[p_id])
        
        g.add((project_uri, RDF.type, BI.Project))
        g.add((project_uri, RDF.type, BI.BioEntity))
        g.add((project_uri, BI.projectId, Literal(p_id, datatype=XSD.string)))
        
        for case_data in project_doc.get("cases", []):
            c_id = case_data.get("case_id")
            case_uri = URIRef(BI[c_id])
            
            g.add((case_uri, RDF.type, BI.Case))
            g.add((case_uri, RDF.type, BI.BioEntity))
            g.add((case_uri, BI.caseId, Literal(c_id, datatype=XSD.string)))
            
            # Relaciones bidireccionales para Q2
            g.add((project_uri, BI.hasCase, case_uri))
            g.add((case_uri, BI.caseInProject, project_uri))

    # 2. Genes y Mediciones (hgnc_genes)
    # Según image_bc7cce.png: projects > cases > case_id > unstranded
    for gene_doc in db["hgnc_genes"].find():
        h_raw = gene_doc["hgnc_id"]
        h_clean = h_raw.replace(":", "_")
        gene_uri = URIRef(BI[h_clean])
        
        g.add((gene_uri, RDF.type, BI.Gene))
        g.add((gene_uri, RDF.type, BI.BioEntity))
        g.add((gene_uri, BI.geneSymbol, Literal(gene_doc["symbol"], datatype=XSD.string)))

        for p_id, proj_data in gene_doc.get("projects", {}).items():
            for c_id, expr in proj_data.get("cases", {}).items():
                meas_uri = URIRef(BI[f"{h_clean}_{p_id}_{c_id}"])
                case_uri = URIRef(BI[c_id])
                
                g.add((meas_uri, RDF.type, BI.ExpressionMeasurement))
                g.add((meas_uri, RDF.type, BI.BioEntity))
                g.add((meas_uri, BI.measuredGene, gene_uri))
                g.add((meas_uri, BI.measuredCase, case_uri))
                
                # Relación para el join de la Q5
                g.add((case_uri, BI.hasCaseMeasurement, meas_uri))
                
                if "unstranded" in expr:
                    g.add((meas_uri, BI.unstrandedCount, Literal(expr["unstranded"], datatype=XSD.decimal)))

    # 3. Proteínas (uniprot_entries)
    # Según image_bc7d62.png: protein.names es un Array
    # Limitamos para evitar archivos gigantes en GitHub
    for prot_doc in db["uniprot_entries"].find().limit(5000):
        u_id = prot_doc["uniprot_id"]
        protein_uri = URIRef(BI[u_id])
        
        g.add((protein_uri, RDF.type, BI.Protein))
        g.add((protein_uri, RDF.type, BI.BioEntity))
        g.add((protein_uri, BI.uniprotId, Literal(u_id, datatype=XSD.string)))
        
        # Mapeamos todos los nombres para que el regex de la Q4 funcione
        names = prot_doc.get("protein", {}).get("names", [])
        for name in names:
            g.add((protein_uri, BI.proteinName, Literal(name, datatype=XSD.string)))

        # Vínculo Gen -> Proteína
        if "gene" in prot_doc and "hgnc_ids" in prot_doc["gene"]:
            for h_id in prot_doc["gene"]["hgnc_ids"]:
                gene_uri = URIRef(BI[h_id.replace(":", "_")])
                g.add((gene_uri, BI.hasProteinProduct, protein_uri))

    # Guardado final
    output_path = ROOT_DIR / "data" / "rdf" / "export.ttl"
    g.serialize(destination=str(output_path), format="turtle")
    print(f"✓ ¡ÉXITO! Grafo generado con {len(g)} tripletas en {output_path}")

if __name__ == "__main__":
    mongo_to_rdf()