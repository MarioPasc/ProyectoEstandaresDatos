import pymongo
from rdflib import Graph, Literal, RDF, URIRef, Namespace
from rdflib.namespace import XSD
from pathlib import Path

# Definir la raíz del proyecto y Namespace
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
BI = Namespace("http://example.org/biointegrate/")

def mongo_to_rdf():
    # Conexión a MongoDB
    client = pymongo.MongoClient("mongodb://localhost:27017/")
    db = client["estandares_db"]
    
    g = Graph()
    g.bind("bi", BI)

    print(f"--- Iniciando transformación Mongo -> RDF ---")
    print(f"Base de datos: {db.name}")

    # A. Proyectos y Casos
    print("Procesando Proyectos y Casos...")
    count_p, count_c = 0, 0
    for project_doc in db["gdc_projects"].find():
        p_id = project_doc['project_id']
        project_uri = URIRef(BI[f"project/{p_id}"])
        g.add((project_uri, RDF.type, BI.Project))
        g.add((project_uri, BI.projectId, Literal(p_id, datatype=XSD.string)))
        count_p += 1

        for case in project_doc.get("cases", []):
            c_id = case['case_id']
            case_uri = URIRef(BI[f"case/{c_id}"])
            g.add((case_uri, RDF.type, BI.Case))
            g.add((case_uri, BI.caseId, Literal(c_id, datatype=XSD.string)))
            g.add((case_uri, BI.caseInProject, project_uri))
            count_c += 1
    print(f"   ✓ {count_p} Proyectos y {count_c} Casos procesados.")

    # B. Genes y Expresión
    print("Procesando Genes y Mediciones de Expresión (esto puede tardar)...")
    count_g, count_e = 0, 0
    for gene_doc in db["hgnc_genes"].find():
        hgnc_raw = gene_doc["hgnc_id"]
        hgnc_clean = hgnc_raw.replace(":", "_")
        gene_uri = URIRef(BI[f"gene/{hgnc_clean}"])
        
        g.add((gene_uri, RDF.type, BI.Gene))
        g.add((gene_uri, BI.geneSymbol, Literal(gene_doc["symbol"], datatype=XSD.string)))
        g.add((gene_uri, BI.hgncId, Literal(hgnc_raw, datatype=XSD.string)))
        count_g += 1

        for proj_id, proj_data in gene_doc.get("projects", {}).items():
            for case_id, expr in proj_data.get("cases", {}).items():
                meas_id = f"{hgnc_clean}_{proj_id}_{case_id}"
                meas_uri = URIRef(BI[f"expression/{meas_id}"])
                g.add((meas_uri, RDF.type, BI.ExpressionMeasurement))
                g.add((meas_uri, BI.measuredGene, gene_uri))
                g.add((meas_uri, BI.measuredCase, URIRef(BI[f"case/{case_id}"])))
                if "unstranded" in expr:
                    g.add((meas_uri, BI.unstrandedCount, Literal(expr["unstranded"], datatype=XSD.decimal)))
                count_e += 1
        
        if count_g % 100 == 0: # Feedback cada 100 genes
            print(f"   ... {count_g} genes analizados...")

    print(f"   ✓ {count_g} Genes y {count_e} Mediciones procesadas.")

    # C. Proteínas
    print("Procesando Proteínas de UniProt...")
    count_pr = 0
    for prot_doc in db["uniprot_entries"].find():
        u_id = prot_doc["uniprot_id"]
        protein_uri = URIRef(BI[f"protein/{u_id}"])
        g.add((protein_uri, RDF.type, BI.Protein))
        g.add((protein_uri, BI.uniprotId, Literal(u_id, datatype=XSD.string)))
        
        if "protein" in prot_doc and "names" in prot_doc["protein"]:
            g.add((protein_uri, BI.proteinName, Literal(prot_doc["protein"]["names"][0], datatype=XSD.string)))

        if "gene" in prot_doc and "hgnc_ids" in prot_doc["gene"]:
            for h_id in prot_doc["gene"]["hgnc_ids"]:
                h_clean = h_id.replace(":", "_")
                g.add((URIRef(BI[f"gene/{h_clean}"]), BI.hasProteinProduct, protein_uri))
        count_pr += 1
    print(f"   ✓ {count_pr} Proteínas procesadas.")

    # Serialización
    print("Guardando archivo Turtle (export.ttl)...")
    output_path = ROOT_DIR / "data" / "rdf" / "export.ttl"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(destination=str(output_path), format="turtle")
    print(f"\n ¡ÉXITO! Grafo generado en: {output_path}")

if __name__ == "__main__":
    mongo_to_rdf()