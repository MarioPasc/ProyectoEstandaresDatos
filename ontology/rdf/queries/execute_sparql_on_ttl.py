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
    parser = argparse.ArgumentParser(description="Execute SPARQL queries against a TTL file.")
    
    parser.add_argument(
        "--ttl-file",
        type=Path,
        default=Path("ontology/data/rdf/biointegrate_data_overlay.ttl"),
        help="Path to the TTL RDF file."
    )
    parser.add_argument(
        "--queries-folder",
        type=Path,
        default=Path("ontology/sparql/queries"),
        help="Directory containing SPARQL queries (.rq files)."
    )
    parser.add_argument(
        "--queries",
        nargs="+",
        help="List of query filenames (without extension) to execute. If not provided, all .rq files in the folder will be executed."
    )
    parser.add_argument(
        "--results-folder",
        type=Path,
        default=Path("ontology/rdf/results"),
        help="Directory to save CSV results."
    )
    
    return parser.parse_args()

def execute_sparql_on_ttl(ttl_file, queries_folder, queries_list, results_folder):
    if not ttl_file.exists():
        logger.error(f"TTL file not found: {ttl_file}")
        return

    logger.info(f"--- Loading Graph ({ttl_file.name}) ---")
    g = rdflib.Graph()
    try:
        g.parse(str(ttl_file), format="turtle")
        logger.info(f"✓ Graph loaded with {len(g)} triples.")
    except Exception as e:
        logger.error(f"Failed to parse TTL file: {e}")
        return

    results_folder.mkdir(parents=True, exist_ok=True)

    # Determine queries to run
    files_to_run = []
    if queries_list:
        for q_name in queries_list:
            # Handle cases where user might provide extension or not
            if q_name.endswith(".rq"):
                q_path = queries_folder / q_name
            else:
                q_path = queries_folder / f"{q_name}.rq"
            
            if q_path.exists():
                files_to_run.append(q_path)
            else:
                logger.warning(f"Query file not found: {q_path}")
    else:
        # Run all .rq files in folder
        if queries_folder.exists():
            files_to_run = sorted(list(queries_folder.glob("*.rq")))
        else:
            logger.error(f"Queries folder not found: {queries_folder}")
            return

    if not files_to_run:
        logger.warning("No queries to execute.")
        return

    for query_path in files_to_run:
        query_name = query_path.stem
        logger.info(f"Executing {query_name}...")
        
        try:
            with open(query_path, 'r', encoding='utf-8') as f:
                query_str = f.read()
            
            results = g.query(query_str)
            
            output_file = results_folder / f"{query_name}_results.csv"
            
            with open(output_file, 'w', newline='', encoding='utf-8') as f_out:
                writer = csv.writer(f_out)
                if results.vars:
                    writer.writerow([str(v) for v in results.vars])
                    for row in results:
                        writer.writerow([str(v) for v in row])
                else:
                    # Handle ASK or CONSTRUCT queries if necessary
                    pass
            
            logger.info(f"   ✓ Saved results to: {output_file}")
            
        except Exception as e:
            logger.error(f"   ❌ Error executing {query_name}: {e}")

if __name__ == "__main__":
    args = parse_args()
    execute_sparql_on_ttl(args.ttl_file, args.queries_folder, args.queries, args.results_folder)