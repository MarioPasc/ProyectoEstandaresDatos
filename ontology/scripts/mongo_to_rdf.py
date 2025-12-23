import pymongo
from rdflib import Graph, Literal, RDF, URIRef, Namespace
from rdflib.namespace import XSD
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
BI = Namespace("http://example.org/biointegrate/")

def mongo_to_rdf():
    client = pymongo.MongoClient("mongodb://localhost:27017/")
    db = client["estandares_db"]
    g = Graph()
    g.bind("bi", BI)

    print("--- Iniciando Población (Corrección de Colecciones) ---")

    # A. Proyectos y Casos (Corregido a gdc_cases)
    print("Mapeando desde gdc_cases...")
    proyectos_procesados = set()
    
    # Buscamos en la colección real que aparece en tu Compass
    for case_doc in db["gdc_cases"].find():
        c_id = case_doc.get('case_id')
        # Buscamos el project_id (normalmente dentro de 'project' o en la raíz)
        p_id = case_doc.get('project', {}).get('project_id') or case_doc.get('project_id')
        
        if not c_id or not p_id: continue

        case_uri = URIRef(BI[f"case/{c_id}"])
        project_uri = URIRef(BI[f"project/{p_id}"])

        # 1. Crear el Proyecto (Clase bi:Project)
        if p_id not in proyectos_procesados:
            g.add((project_uri, RDF.type, BI.BioEntity))
            g.add((project_uri, RDF.type, BI.Project))
            g.add((project_uri, BI.projectId, Literal(p_id, datatype=XSD.string)))
            proyectos_procesados.add(p_id)

        # 2. Crear el Caso (Clase bi:Case)
        g.add((case_uri, RDF.type, BI.BioEntity))
        g.add((case_uri, RDF.type, BI.Case))
        g.add((case_uri, BI.caseId, Literal(c_id, datatype=XSD.string)))
        g.add((case_uri, BI.caseInProject, project_uri))

    # B. Genes y Mediciones (hgnc_genes)
    print("Mapeando Genes y Mediciones...")
    for gene_doc in db["hgnc_genes"].find():
        h_raw = gene_doc["hgnc_id"]
        h_clean = h_raw.replace(":", "_")
        gene_uri = URIRef(BI[f"gene/{h_clean}"])
        
        g.add((gene_uri, RDF.type, BI.BioEntity))
        g.add((gene_uri, RDF.type, BI.Gene))
        g.add((gene_uri, BI.geneSymbol, Literal(gene_doc["symbol"], datatype=XSD.string)))

        for p_id, p_data in gene_doc.get("projects", {}).items():
            for c_id, expr in p_data.get("cases", {}).items():
                meas_uri = URIRef(BI[f"expression/{h_clean}_{p_id}_{c_id}"])
                g.add((meas_uri, RDF.type, BI.BioEntity))
                g.add((meas_uri, RDF.type, BI.ExpressionMeasurement))
                g.add((meas_uri, BI.measuredGene, gene_uri))
                g.add((meas_uri, BI.measuredCase, URIRef(BI[f"case/{c_id}"])))
                if "unstranded" in expr:
                    g.add((meas_uri, BI.unstrandedCount, Literal(expr["unstranded"], datatype=XSD.decimal)))

    # C. Proteínas (uniprot_entries)
    print("Mapeando Proteínas...")
    for prot_doc in db["uniprot_entries"].find():
        u_uri = URIRef(BI[f"protein/{prot_doc['uniprot_id']}"])
        g.add((u_uri, RDF.type, BI.BioEntity))
        g.add((u_uri, RDF.type, BI.Protein))
        g.add((u_uri, BI.uniprotId, Literal(prot_doc['uniprot_id'], datatype=XSD.string)))

    # Guardar Grafo
    output_path = ROOT_DIR / "data" / "rdf" / "export.ttl"
    g.serialize(destination=str(output_path), format="turtle")
    print(f"✓ ÉXITO: {len(g)} tripletas generadas.")

if __name__ == "__main__":
    mongo_to_rdf()