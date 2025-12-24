import logging
import sys
import argparse
from pathlib import Path
from typing import Dict, Set, Any, List

import pymongo
from rdflib import Graph, Literal, RDF, URIRef, Namespace
from rdflib.namespace import XSD, OWL

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Namespaces
BI_NS = "http://example.org/biointegrate/"
BI = Namespace(BI_NS)

def parse_args():
    parser = argparse.ArgumentParser(description="Generate coherent TTL from MongoDB based on OWL entities.")
    parser.add_argument(
        "--owl-file",
        type=Path,
        default=Path("ontology/data/owl/biointegrate-ontology-reasoned.owl"),
        help="Path to the input OWL ontology file."
    )
    parser.add_argument(
        "--output-ttl",
        type=Path,
        default=Path("ontology/data/rdf/biointegrate_data_overlay.ttl"),
        help="Path to the output TTL file."
    )
    return parser.parse_args()

def extract_ids_from_owl(owl_file_path: Path) -> Dict[str, Set[str]]:
    """
    Parses the OWL file to extract unique identifiers for Genes, Proteins, Cases, and Projects.
    
    Returns:
        Dict with keys 'genes', 'proteins', 'cases', 'projects' containing sets of IDs.
    """
    logger.info(f"Parsing OWL file: {owl_file_path}")
    if not owl_file_path.exists():
        raise FileNotFoundError(f"OWL file not found at {owl_file_path}")

    g = Graph()
    
    # Try parsing as RDF/XML first (standard for .owl), then fallback to Turtle
    try:
        logger.info("Attempting to parse as RDF/XML...")
        g.parse(str(owl_file_path), format="xml")
    except Exception as e_xml:
        logger.warning(f"RDF/XML parsing failed ({e_xml}). Attempting Turtle...")
        try:
            g = Graph() # Reset graph
            g.parse(str(owl_file_path), format="turtle")
        except Exception as e_turtle:
            logger.error(f"Failed to parse OWL file as RDF/XML or Turtle.")
            raise e_turtle

    ids = {
        "genes": set(),
        "proteins": set(),
        "cases": set(),
        "projects": set()
    }

    # Iterate over all subjects in the graph
    for subject in g.subjects(unique=True):
        s_str = str(subject)
        if not s_str.startswith(BI_NS):
            continue
            
        # Extract local part
        local_part = s_str.replace(BI_NS, "")
        
        # Analyze patterns based on the known URI structure: type/ID
        parts = local_part.split("/")
        if len(parts) < 2:
            continue
            
        entity_type = parts[0]
        entity_id = parts[1]

        if entity_type == "gene":
            # Convert HGNC_1234 back to HGNC:1234 for MongoDB querying
            ids["genes"].add(entity_id.replace("_", ":"))
        elif entity_type == "protein":
            ids["proteins"].add(entity_id)
        elif entity_type == "case":
            ids["cases"].add(entity_id)
        elif entity_type == "project":
            ids["projects"].add(entity_id)
            
    logger.info(f"Extracted {len(ids['genes'])} Genes, {len(ids['proteins'])} Proteins, "
                f"{len(ids['cases'])} Cases, {len(ids['projects'])} Projects from OWL.")
    
    # Log examples
    if ids["genes"]:
        logger.info(f"Example Genes from OWL: {list(ids['genes'])[:3]}")
    if ids["proteins"]:
        logger.info(f"Example Proteins from OWL: {list(ids['proteins'])[:3]}")
    if ids["cases"]:
        logger.info(f"Example Cases from OWL: {list(ids['cases'])[:3]}")
        
    return ids

def fetch_mongo_data(ids_map: Dict[str, Set[str]]) -> Dict[str, List[Any]]:
    """
    Queries MongoDB for the specific IDs extracted from the OWL.
    """
    logger.info("Connecting to MongoDB...")
    client = pymongo.MongoClient("mongodb://localhost:27017/")
    db = client["estandares_db"]
    
    data = {
        "genes": [],
        "proteins": [],
        "projects": [] # Cases are usually nested in projects in GDC structure
    }

    # 1. Fetch Genes
    if ids_map["genes"]:
        logger.info("Fetching Genes from MongoDB...")
        genes_cursor = db["hgnc_genes"].find({"hgnc_id": {"$in": list(ids_map["genes"])}})
        data["genes"] = list(genes_cursor)
        logger.info(f"Fetched {len(data['genes'])} Genes from MongoDB.")
        if data["genes"]:
            logger.info(f"Example Gene from MongoDB: {data['genes'][0].get('hgnc_id')}")

    # 2. Fetch Proteins
    if ids_map["proteins"]:
        logger.info("Fetching Proteins from MongoDB...")
        proteins_cursor = db["uniprot_entries"].find({"uniprot_id": {"$in": list(ids_map["proteins"])}})
        data["proteins"] = list(proteins_cursor)
        logger.info(f"Fetched {len(data['proteins'])} Proteins from MongoDB.")
        if data["proteins"]:
            logger.info(f"Example Protein from MongoDB: {data['proteins'][0].get('uniprot_id')}")

    # 3. Fetch Projects (and Cases)
    # Since cases are nested in projects in the 'gdc_cases' collection (based on previous script),
    # we fetch the projects that are in our list.
    if ids_map["projects"]:
        logger.info("Fetching Projects/Cases from MongoDB...")
        # We fetch the whole project document. We will filter cases in memory or via projection if needed.
        # Given the structure, it's safer to fetch the project and filter cases in the loop.
        projects_cursor = db["gdc_cases"].find({"project_id": {"$in": list(ids_map["projects"])}})
        data["projects"] = list(projects_cursor)
        logger.info(f"Fetched {len(data['projects'])} Projects from MongoDB.")
        if data["projects"]:
            logger.info(f"Example Project from MongoDB: {data['projects'][0].get('project_id')}")

    client.close()
    return data

def generate_coherent_ttl(data: Dict[str, List[Any]], ids_map: Dict[str, Set[str]]) -> Graph:
    """
    Generates an RDF graph containing data only for the entities present in the OWL.
    """
    logger.info("Generating RDF Graph...")
    g = Graph()
    g.bind("bio", BI)
    g.bind("owl", OWL)

    # Helper to create URIs matching the OWL pattern
    def make_uri(entity_type, entity_id):
        return URIRef(f"{BI_NS}{entity_type}/{entity_id}")

    # Counters for logging
    counts = {
        "projects": 0,
        "cases": 0,
        "genes": 0,
        "measurements": 0,
        "proteins": 0,
        "organisms": 0,
        "goterms": 0
    }

    # 1. Process Projects and Cases
    for project_doc in data["projects"]:
        p_id = project_doc.get("project_id")
        if p_id not in ids_map["projects"]:
            continue
            
        project_uri = make_uri("project", p_id)
        g.add((project_uri, RDF.type, BI.Project))
        g.add((project_uri, RDF.type, OWL.NamedIndividual))
        g.add((project_uri, BI.projectId, Literal(p_id)))
        counts["projects"] += 1
        
        # Process Cases within Project
        for case_data in project_doc.get("cases", []):
            c_id = case_data.get("case_id")
            if c_id in ids_map["cases"]:
                case_uri = make_uri("case", c_id)
                g.add((case_uri, RDF.type, BI.Case))
                g.add((case_uri, RDF.type, OWL.NamedIndividual))
                g.add((case_uri, BI.caseId, Literal(c_id)))
                counts["cases"] += 1
                
                # Link Project and Case
                g.add((project_uri, BI.hasCase, case_uri))
                g.add((case_uri, BI.caseInProject, project_uri))
                
                # Add extra case metadata if available
                if "disease_type" in project_doc:
                     g.add((case_uri, BI.diseaseTypeLabel, Literal(project_doc["disease_type"])))
                if "primary_site" in project_doc:
                     g.add((case_uri, BI.primarySiteLabel, Literal(project_doc["primary_site"])))

    # 2. Process Genes and Measurements
    for gene_doc in data["genes"]:
        h_id_original = gene_doc["hgnc_id"]
        h_id_sanitized = h_id_original.replace(":", "_")
        
        gene_uri = make_uri("gene", h_id_sanitized)
        g.add((gene_uri, RDF.type, BI.Gene))
        g.add((gene_uri, RDF.type, OWL.NamedIndividual))
        g.add((gene_uri, BI.hgncId, Literal(h_id_original))) # Keep original ID as literal
        g.add((gene_uri, BI.geneSymbol, Literal(gene_doc.get("symbol", ""))))
        counts["genes"] += 1

        if "name" in gene_doc:
            g.add((gene_uri, BI.geneName, Literal(gene_doc["name"])))
        if "locus_group" in gene_doc:
            g.add((gene_uri, BI.locusGroup, Literal(gene_doc["locus_group"])))
        if "ensembl_gene_id" in gene_doc:
            g.add((gene_uri, BI.ensemblGeneId, Literal(gene_doc["ensembl_gene_id"])))

        # Process Measurements (Intersection of Gene x Project x Case)
        # We only add measurements if the Case and Project are also in our OWL scope
        for p_id, proj_data in gene_doc.get("projects", {}).items():
            if p_id not in ids_map["projects"]:
                continue
                
            for c_id, expr in proj_data.get("cases", {}).items():
                if c_id not in ids_map["cases"]:
                    continue
                
                # Construct Measurement URI
                # Pattern from OWL seems to be: expression/HGNC_ID_ProjectID_CaseID
                meas_id = f"{h_id_sanitized}_{p_id}_{c_id}"
                meas_uri = make_uri("expression", meas_id)
                
                g.add((meas_uri, RDF.type, BI.ExpressionMeasurement))
                g.add((meas_uri, RDF.type, OWL.NamedIndividual))
                g.add((meas_uri, BI.measuredGene, gene_uri))
                g.add((meas_uri, BI.measuredCase, make_uri("case", c_id)))
                g.add((meas_uri, BI.measuredProject, make_uri("project", p_id)))
                counts["measurements"] += 1
                
                # Inverse links
                g.add((make_uri("case", c_id), BI.hasCaseMeasurement, meas_uri))
                g.add((gene_uri, BI.hasGeneMeasurement, meas_uri))
                g.add((make_uri("project", p_id), BI.hasProjectMeasurement, meas_uri))

                # Data properties
                if "file_id" in expr:
                    g.add((meas_uri, BI.fileId, Literal(expr["file_id"])))
                if "unstranded" in expr:
                    g.add((meas_uri, BI.unstrandedCount, Literal(expr["unstranded"], datatype=XSD.decimal)))
                if "stranded_first" in expr:
                    g.add((meas_uri, BI.strandedFirstCount, Literal(expr["stranded_first"], datatype=XSD.decimal)))
                if "stranded_second" in expr:
                    g.add((meas_uri, BI.strandedSecondCount, Literal(expr["stranded_second"], datatype=XSD.decimal)))
                if "tpm_unstranded" in expr:
                    g.add((meas_uri, BI.tpmUnstranded, Literal(expr["tpm_unstranded"], datatype=XSD.decimal)))
                if "fpkm_unstranded" in expr:
                    g.add((meas_uri, BI.fpkmUnstranded, Literal(expr["fpkm_unstranded"], datatype=XSD.decimal)))
                if "fpkm_uq_unstranded" in expr:
                    g.add((meas_uri, BI.fpkmUqUnstranded, Literal(expr["fpkm_uq_unstranded"], datatype=XSD.decimal)))

    # 3. Process Proteins
    for prot_doc in data["proteins"]:
        u_id = prot_doc["uniprot_id"]
        protein_uri = make_uri("protein", u_id)
        
        g.add((protein_uri, RDF.type, BI.Protein))
        g.add((protein_uri, RDF.type, OWL.NamedIndividual))
        g.add((protein_uri, BI.uniprotId, Literal(u_id)))
        counts["proteins"] += 1
        
        # Names
        names = prot_doc.get("protein", {}).get("names", [])
        for name in names:
            g.add((protein_uri, BI.proteinName, Literal(name)))
            
        # Sequence Length
        length = prot_doc.get("protein", {}).get("length")
        if length:
            g.add((protein_uri, BI.sequenceLength, Literal(length, datatype=XSD.integer)))
            
        # Function
        func_cc = prot_doc.get("protein", {}).get("function_cc")
        if func_cc:
            g.add((protein_uri, BI.functionText, Literal(func_cc[:500]))) # Truncate if too long

        # Link to Genes
        # Note: We only link to genes that are in our scope
        for h_id in prot_doc.get("gene", {}).get("hgnc_ids", []):
            if h_id in ids_map["genes"]:
                gene_uri = make_uri("gene", h_id.replace(":", "_"))
                g.add((gene_uri, BI.hasProteinProduct, protein_uri))
                g.add((protein_uri, BI.proteinProductOf, gene_uri))

        # Process Organism
        organism_data = prot_doc.get("organism", {})
        if organism_data:
            tax_id = organism_data.get("taxonomy_id")
            if tax_id:
                org_uri = make_uri("organism", str(tax_id))
                
                # Add Organism entity if not exists
                if (org_uri, RDF.type, BI.Organism) not in g:
                    g.add((org_uri, RDF.type, BI.Organism))
                    g.add((org_uri, RDF.type, OWL.NamedIndividual))
                    g.add((org_uri, BI.taxonomyId, Literal(tax_id, datatype=XSD.integer)))
                    
                    sci_name = organism_data.get("scientific_name") or organism_data.get("name")
                    if sci_name:
                        g.add((org_uri, BI.scientificName, Literal(sci_name)))
                    
                    counts["organisms"] += 1
                
                # Link Protein to Organism
                g.add((protein_uri, BI.hasOrganism, org_uri))

        # Process GO Terms
        go_terms = prot_doc.get("go_terms", {})
        
        # Helper to add GO term
        def add_go_term(term_entry, predicate, aspect_code):
            # term_entry can be a string "Label [GO:ID]" or a dict
            term_str = term_entry.get("term") if isinstance(term_entry, dict) else term_entry
            if not term_str:
                return

            # Extract ID and Label
            # Expected format: "cytoplasm [GO:0005737]"
            import re
            match = re.search(r'\[GO:(\d+)\]', term_str)
            if not match:
                return
            
            go_id_numeric = match.group(1)
            go_id = f"GO_{go_id_numeric}"
            go_uri = make_uri("goterm", go_id)
            
            # Add GO Term entity if not exists (rdflib handles duplicates in graph)
            if (go_uri, RDF.type, BI.GOTerm) not in g:
                g.add((go_uri, RDF.type, BI.GOTerm))
                g.add((go_uri, RDF.type, OWL.NamedIndividual))
                g.add((go_uri, BI.goId, Literal(f"GO:{go_id_numeric}")))
                g.add((go_uri, BI.goAspect, Literal(aspect_code)))
                
                # Extract label
                label_match = re.match(r'^(.+?)\s*\[GO:\d+\]$', term_str)
                if label_match:
                    g.add((go_uri, BI.goLabel, Literal(label_match.group(1).strip())))
                
                counts["goterms"] += 1
            
            # Link Protein to GO Term
            g.add((protein_uri, predicate, go_uri))

        # Molecular Function
        for item in go_terms.get("molecular_function", []):
            add_go_term(item, BI.hasMolecularFunction, "MF")
            
        # Biological Process
        for item in go_terms.get("biological_process", []):
            add_go_term(item, BI.hasBiologicalProcess, "BP")
            
        # Cellular Component
        for item in go_terms.get("cellular_component", []):
            add_go_term(item, BI.hasCellularComponent, "CC")

    logger.info(f"Generated TTL Graph with: {counts['projects']} Projects, {counts['cases']} Cases, "
                f"{counts['genes']} Genes, {counts['proteins']} Proteins, {counts['measurements']} Measurements, "
                f"{counts['organisms']} Organisms, {counts['goterms']} GO Terms.")
    return g

def validate_coherence(ids_map: Dict[str, Set[str]], graph: Graph):
    """
    Checks if the generated graph covers the requested OWL entities.
    """
    logger.info("Validating coherence between OWL request and TTL output...")
    
    generated_subjects = set(str(s) for s in graph.subjects())
    
    missing = {k: [] for k in ids_map}
    
    # Check Genes
    for gid in ids_map["genes"]:
        uri = f"{BI_NS}gene/{gid.replace(':', '_')}"
        if uri not in generated_subjects:
            missing["genes"].append(gid)
            
    # Check Proteins
    for pid in ids_map["proteins"]:
        uri = f"{BI_NS}protein/{pid}"
        if uri not in generated_subjects:
            missing["proteins"].append(pid)
            
    # Check Cases
    for cid in ids_map["cases"]:
        uri = f"{BI_NS}case/{cid}"
        if uri not in generated_subjects:
            missing["cases"].append(cid)

    # Report
    total_requested = sum(len(v) for v in ids_map.values())
    total_missing = sum(len(v) for v in missing.values())
    
    if total_missing == 0:
        logger.info("SUCCESS: 100% Coherence. All OWL entities found in MongoDB and exported to TTL.")
    else:
        logger.warning(f"WARNING: {total_missing} entities from OWL were NOT found in MongoDB or failed to export.")
        for k, v in missing.items():
            if v:
                logger.warning(f"  Missing {k}: {len(v)} (e.g., {v[:3]}...)")

def main():
    args = parse_args()
    try:
        # 1. Extract IDs from OWL
        ids_map = extract_ids_from_owl(args.owl_file)
        
        # 2. Fetch Data from MongoDB
        mongo_data = fetch_mongo_data(ids_map)
        
        # 3. Generate TTL
        ttl_graph = generate_coherent_ttl(mongo_data, ids_map)
        
        # 4. Validate
        validate_coherence(ids_map, ttl_graph)
        
        # 5. Save
        args.output_ttl.parent.mkdir(parents=True, exist_ok=True)
        ttl_graph.serialize(destination=str(args.output_ttl), format="turtle")
        logger.info(f"TTL file saved to: {args.output_ttl}")
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
