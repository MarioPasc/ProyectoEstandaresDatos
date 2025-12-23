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

    print("--- Iniciando Población del Grafo ---")

    # A. Proyectos y Casos (gdc_cases)
    # Según image_bba2ee.png, cada documento es un proyecto con un array 'cases'
    print("Procesando colección 'gdc_cases'...")
    p_count, c_count = 0, 0
    
    for project_doc in db["gdc_cases"].find():
        p_id = project_doc.get("project_id")
        if not p_id: continue
        
        project_uri = URIRef(BI[p_id])
        g.add((project_uri, RDF.type, BI.Project))
        g.add((project_uri, RDF.type, BI.BioEntity))
        g.add((project_uri, BI.projectId, Literal(p_id, datatype=XSD.string)))
        p_count += 1
        
        # Entramos en el array de casos
        for case_data in project_doc.get("cases", []):
            c_id = case_data.get("case_id")
            if not c_id: continue
            
            case_uri = URIRef(BI[c_id])
            g.add((case_uri, RDF.type, BI.Case))
            g.add((case_uri, RDF.type, BI.BioEntity))
            g.add((case_uri, BI.caseId, Literal(c_id, datatype=XSD.string)))
            
            # Relación necesaria para la Q2
            g.add((project_uri, BI.hasCase, case_uri))
            c_count += 1

    print(f"✓ Mapeados {p_count} Proyectos y {c_count} Casos.")

    # B. Genes y Mediciones (hgnc_genes)
    print("Procesando colección 'hgnc_genes'...")
    g_count, m_count = 0, 0
    for gene_doc in db["hgnc_genes"].find():
        h_id = gene_doc["hgnc_id"].replace(":", "_")
        gene_uri = URIRef(BI[h_id])
        
        g.add((gene_uri, RDF.type, BI.Gene))
        g.add((gene_uri, RDF.type, BI.BioEntity))
        g.add((gene_uri, BI.geneSymbol, Literal(gene_doc["symbol"], datatype=XSD.string)))
        g_count += 1

        for proj_id, proj_data in gene_doc.get("projects", {}).items():
            for case_id, expr in proj_data.get("cases", {}).items():
                # IRI similar a la vista en Protégé (image_baba55.jpg)
                meas_id = f"{h_id}_{proj_id}_{case_id}"
                meas_uri = URIRef(BI[meas_id])
                case_uri = URIRef(BI[case_id])
                
                g.add((meas_uri, RDF.type, BI.ExpressionMeasurement))
                g.add((meas_uri, RDF.type, BI.BioEntity))
                g.add((meas_uri, BI.measuredGene, gene_uri))
                g.add((meas_uri, BI.measuredCase, case_uri))
                
                # Relación necesaria para la Q5
                g.add((case_uri, BI.hasCaseMeasurement, meas_uri))
                
                if "unstranded" in expr:
                    g.add((meas_uri, BI.unstrandedCount, Literal(expr["unstranded"], datatype=XSD.decimal)))
                m_count += 1

    print(f"✓ Mapeados {g_count} Genes y {m_count} Mediciones.")

    # C. Proteínas (uniprot_entries)
    print("Procesando colección 'uniprot_entries'...")
    for prot_doc in db["uniprot_entries"].find():
        u_id = prot_doc["uniprot_id"]
        protein_uri = URIRef(BI[u_id])
        g.add((protein_uri, RDF.type, BI.Protein))
        g.add((protein_uri, RDF.type, BI.BioEntity))
        g.add((protein_uri, BI.uniprotId, Literal(u_id, datatype=XSD.string)))
        
        if "protein" in prot_doc and "names" in prot_doc["protein"]:
            g.add((protein_uri, BI.proteinName, Literal(prot_doc["protein"]["names"][0], datatype=XSD.string)))

        if "gene" in prot_doc and "hgnc_ids" in prot_doc["gene"]:
            for h_id in prot_doc["gene"]["hgnc_ids"]:
                g.add((URIRef(BI[h_id.replace(":", "_")]), BI.hasProteinProduct, protein_uri))

    # Guardar
    output_path = ROOT_DIR / "data" / "rdf" / "export.ttl"
    g.serialize(destination=str(output_path), format="turtle")
    print(f"\n Grafo generado con éxito en: {output_path}")

if __name__ == "__main__":
    mongo_to_rdf()