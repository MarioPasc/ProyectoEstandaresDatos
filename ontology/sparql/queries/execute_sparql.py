import rdflib
import csv
import argparse
import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def parse_args():
    parser = argparse.ArgumentParser(description="Execute SPARQL queries against an OWL ontology.")
    
    parser.add_argument(
        "--owl-file",
        type=Path,
        default=Path("ontology/data/owl/biointegrate-ontology-reasoned.owl"),
        help="Path to the OWL ontology file."
    )
    parser.add_argument(
        "--queries-dir",
        type=Path,
        default=Path("ontology/sparql/queries"),
        help="Directory containing SPARQL queries."
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("ontology/sparql/results"),
        help="Directory to save results."
    )
    
    return parser.parse_args()

def execute_sparql_queries(owl_file, queries_dir, output_dir):
    # Validation
    if not owl_file.exists():
        logger.error(f"OWL file not found at: {owl_file}")
        logger.info("Please verify the path to the ontology file.")
        return

    logger.info("--- Starting SPARQL queries execution ---")
    logger.info(f"OWL File: {owl_file}")
    logger.info(f"Queries Dir: {queries_dir}")
    logger.info(f"Output Dir: {output_dir}")
    
    g = rdflib.Graph()
    try:
        logger.info(f"Loading ontology from {owl_file.name}...")
        try:
            g.parse(str(owl_file), format="xml")
        except Exception as e_xml:
            logger.warning(f"RDF/XML parsing failed ({e_xml}). Attempting Turtle...")
            g = rdflib.Graph()  # Reset graph
            g.parse(str(owl_file), format="turtle")
            
        logger.info("✓ Ontology loaded successfully into memory.")
    except Exception as e:
        logger.error(f"✗ Error loading OWL: {e}")
        return

    # Create results directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Process queries 1 to 6
    for i in range(1, 7):
        query_file = f"q0{i}.rq"
        query_path = queries_dir / query_file
        
        if query_path.exists():
            logger.info(f"Executing {query_file}...")
            try:
                with open(query_path, 'r', encoding='utf-8') as f:
                    query_str = f.read()
                
                results = g.query(query_str)
                
                output_file = output_dir / f"q0{i}_results.csv"
                with open(output_file, 'w', newline='', encoding='utf-8') as f_out:
                    writer = csv.writer(f_out)
                    if results.vars:
                        writer.writerow([str(v) for v in results.vars])
                        for row in results:
                            writer.writerow([str(v) for v in row])
                    else:
                        pass
                
                logger.info(f"   ✓ Success. Saved to: {output_file}")
            except Exception as e:
                logger.error(f"   ✗ Error in {query_file}: {e}")
        else:
            logger.warning(f"⚠ Warning: {query_file} not found in {queries_dir}")

if __name__ == "__main__":
    args = parse_args()
    execute_sparql_queries(args.owl_file, args.queries_dir, args.results_dir)