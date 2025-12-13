"""
json_to_owl.py

Script to parse JSON output from Query6 (OntologyIndividual) and insert
individuals into the BioIntegrate OWL ontology.

Usage:
    python ontology/scripts/json_to_owl.py \
        --input docs/t2-resultados/json/query_6_ontology_individual.json \
        --ontology ontology/assets/biointegrate.owl \
        --output ontology/assets/biointegrate_populated.owl

    # Or using the installed command:
    biointegrate-populate-ontology \
        --input docs/t2-resultados/json/query_6_ontology_individual.json \
        --ontology ontology/assets/biointegrate.owl \
        --output ontology/assets/biointegrate_populated.owl

Issue: #39 - T3 - Ontology Population from MongoDB
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from decimal import Decimal

from rdflib import Graph, Namespace, Literal, URIRef, RDF, XSD


# Define namespaces
BIO = Namespace("http://example.org/biointegrate/")
OWL = Namespace("http://www.w3.org/2002/07/owl#")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Populate BioIntegrate ontology with individuals from JSON query results',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Populate ontology from a single JSON file
  %(prog)s --input query_result.json --ontology biointegrate.owl --output populated.owl

  # Append to existing populated ontology
  %(prog)s --input query_result.json --ontology populated.owl --output populated.owl

  # Process multiple JSON files
  %(prog)s --input result1.json result2.json --ontology biointegrate.owl --output populated.owl
"""
    )
    
    parser.add_argument(
        '--input', '-i',
        type=str,
        nargs='+',
        required=True,
        help='Path(s) to JSON file(s) containing query results from Query6'
    )
    
    parser.add_argument(
        '--ontology', '-o',
        type=str,
        required=True,
        help='Path to the base OWL ontology file (biointegrate.owl)'
    )
    
    parser.add_argument(
        '--output', '-O',
        type=str,
        required=True,
        help='Path to save the populated OWL ontology'
    )
    
    parser.add_argument(
        '--format',
        type=str,
        default='turtle',
        choices=['turtle', 'xml', 'n3', 'nt'],
        help='Output format for the ontology (default: turtle)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    return parser.parse_args()


def sanitize_iri_fragment(text: str) -> str:
    """
    Sanitize a string to be used as an IRI fragment.
    Replaces invalid characters with underscores.
    """
    # Replace colons and other special characters
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', text)
    return sanitized


def extract_go_id(go_term: str) -> Optional[str]:
    """
    Extract GO ID from a GO term string like 'cytoplasm [GO:0005737]'.
    Returns the GO ID (e.g., 'GO_0005737') or None if not found.
    """
    match = re.search(r'\[GO:(\d+)\]', go_term)
    if match:
        return f"GO_{match.group(1)}"
    return None


def extract_go_label(go_term: str) -> str:
    """
    Extract the label from a GO term string like 'cytoplasm [GO:0005737]'.
    Returns the label (e.g., 'cytoplasm').
    """
    match = re.match(r'^(.+?)\s*\[GO:\d+\]$', go_term)
    if match:
        return match.group(1).strip()
    return go_term


def add_gene_individual(graph: Graph, gene_data: Dict[str, Any], verbose: bool = False) -> URIRef:
    """Add a Gene individual to the graph."""
    # Create gene IRI from HGNC ID
    hgnc_id = gene_data.get('bio:hgncId', '')
    gene_iri_fragment = sanitize_iri_fragment(hgnc_id)
    gene_uri = BIO[f"gene/{gene_iri_fragment}"]
    
    # Add type assertion
    graph.add((gene_uri, RDF.type, BIO.Gene))
    graph.add((gene_uri, RDF.type, OWL.NamedIndividual))
    
    # Add data properties
    if hgnc_id:
        graph.add((gene_uri, BIO.hgncId, Literal(hgnc_id, datatype=XSD.string)))
    
    gene_symbol = gene_data.get('bio:geneSymbol')
    if gene_symbol:
        graph.add((gene_uri, BIO.geneSymbol, Literal(gene_symbol, datatype=XSD.string)))
    
    gene_name = gene_data.get('bio:geneName')
    if gene_name:
        graph.add((gene_uri, BIO.geneName, Literal(gene_name, datatype=XSD.string)))
    
    ensembl_id = gene_data.get('bio:ensemblGeneId')
    if ensembl_id:
        graph.add((gene_uri, BIO.ensemblGeneId, Literal(ensembl_id, datatype=XSD.string)))
    
    locus_group = gene_data.get('bio:locusGroup')
    if locus_group:
        graph.add((gene_uri, BIO.locusGroup, Literal(locus_group, datatype=XSD.string)))
    
    if verbose:
        print(f"  Added Gene: {gene_symbol} ({hgnc_id})")
    
    return gene_uri


def add_organism_individual(graph: Graph, organism_data: Dict[str, Any], verbose: bool = False) -> URIRef:
    """Add an Organism individual to the graph."""
    taxonomy_id = organism_data.get('organism_properties', {}).get('bio:taxonomyId')
    
    if not taxonomy_id:
        return None
    
    organism_uri = BIO[f"organism/{taxonomy_id}"]
    
    # Check if already exists (avoid duplicates)
    if (organism_uri, RDF.type, BIO.Organism) in graph:
        return organism_uri
    
    # Add type assertion
    graph.add((organism_uri, RDF.type, BIO.Organism))
    graph.add((organism_uri, RDF.type, OWL.NamedIndividual))
    
    # Add data properties
    graph.add((organism_uri, BIO.taxonomyId, Literal(taxonomy_id, datatype=XSD.integer)))
    
    scientific_name = organism_data.get('organism_properties', {}).get('bio:scientificName')
    if scientific_name:
        graph.add((organism_uri, BIO.scientificName, Literal(scientific_name, datatype=XSD.string)))
    
    if verbose:
        print(f"  Added Organism: {scientific_name} (taxon:{taxonomy_id})")
    
    return organism_uri


def add_go_term_individual(graph: Graph, go_term_str: str, aspect: str, verbose: bool = False) -> Optional[URIRef]:
    """Add a GOTerm individual to the graph."""
    go_id = extract_go_id(go_term_str)
    if not go_id:
        return None
    
    go_uri = BIO[f"goterm/{go_id}"]
    
    # Check if already exists (avoid duplicates)
    if (go_uri, RDF.type, BIO.GOTerm) in graph:
        return go_uri
    
    # Add type assertion
    graph.add((go_uri, RDF.type, BIO.GOTerm))
    graph.add((go_uri, RDF.type, OWL.NamedIndividual))
    
    # Add data properties
    graph.add((go_uri, BIO.goId, Literal(go_id.replace('_', ':'), datatype=XSD.string)))
    
    go_label = extract_go_label(go_term_str)
    if go_label:
        graph.add((go_uri, BIO.goLabel, Literal(go_label, datatype=XSD.string)))
    
    graph.add((go_uri, BIO.goAspect, Literal(aspect, datatype=XSD.string)))
    
    if verbose:
        print(f"  Added GOTerm: {go_label} ({go_id})")
    
    return go_uri


def add_protein_individual(
    graph: Graph, 
    protein_data: Dict[str, Any], 
    gene_uri: URIRef,
    verbose: bool = False
) -> URIRef:
    """Add a Protein individual to the graph with all its relationships."""
    protein_props = protein_data.get('protein_properties', {})
    uniprot_id = protein_props.get('bio:uniprotId', '')
    
    protein_uri = BIO[f"protein/{uniprot_id}"]
    
    # Add type assertion
    graph.add((protein_uri, RDF.type, BIO.Protein))
    graph.add((protein_uri, RDF.type, OWL.NamedIndividual))
    
    # Add data properties
    if uniprot_id:
        graph.add((protein_uri, BIO.uniprotId, Literal(uniprot_id, datatype=XSD.string)))
    
    protein_names = protein_props.get('bio:proteinName', [])
    if isinstance(protein_names, list):
        for name in protein_names:
            if name:
                graph.add((protein_uri, BIO.proteinName, Literal(name, datatype=XSD.string)))
    elif protein_names:
        graph.add((protein_uri, BIO.proteinName, Literal(protein_names, datatype=XSD.string)))
    
    seq_length = protein_props.get('bio:sequenceLength')
    if seq_length is not None:
        graph.add((protein_uri, BIO.sequenceLength, Literal(seq_length, datatype=XSD.integer)))
    
    function_text = protein_props.get('bio:functionText')
    if function_text:
        graph.add((protein_uri, BIO.functionText, Literal(function_text, datatype=XSD.string)))
    
    # Add object property: proteinProductOf (inverse of hasProteinProduct)
    graph.add((protein_uri, BIO.proteinProductOf, gene_uri))
    graph.add((gene_uri, BIO.hasProteinProduct, protein_uri))
    
    # Add organism relationship
    organism_data = protein_data.get('organism', {})
    if organism_data:
        organism_uri = add_organism_individual(graph, organism_data, verbose)
        if organism_uri:
            graph.add((protein_uri, BIO.hasOrganism, organism_uri))
    
    # Add GO term relationships
    go_terms = protein_data.get('go_terms', {})
    
    # Molecular function
    for go_term in go_terms.get('molecular_function', []):
        if isinstance(go_term, dict):
            go_term_str = go_term.get('term', '')
        else:
            go_term_str = go_term
        if go_term_str:
            go_uri = add_go_term_individual(graph, go_term_str, 'MF', verbose)
            if go_uri:
                graph.add((protein_uri, BIO.hasMolecularFunction, go_uri))
    
    # Biological process
    for go_term in go_terms.get('biological_process', []):
        if isinstance(go_term, dict):
            go_term_str = go_term.get('term', '')
        else:
            go_term_str = go_term
        if go_term_str:
            go_uri = add_go_term_individual(graph, go_term_str, 'BP', verbose)
            if go_uri:
                graph.add((protein_uri, BIO.hasBiologicalProcess, go_uri))
    
    # Cellular component
    for go_term in go_terms.get('cellular_component', []):
        if isinstance(go_term, dict):
            go_term_str = go_term.get('term', '')
        else:
            go_term_str = go_term
        if go_term_str:
            go_uri = add_go_term_individual(graph, go_term_str, 'CC', verbose)
            if go_uri:
                graph.add((protein_uri, BIO.hasCellularComponent, go_uri))
    
    if verbose:
        print(f"  Added Protein: {uniprot_id}")
    
    return protein_uri


def add_project_individual(graph: Graph, project_id: str, verbose: bool = False) -> URIRef:
    """Add a Project individual to the graph."""
    project_uri = BIO[f"project/{project_id}"]
    
    # Check if already exists (avoid duplicates)
    if (project_uri, RDF.type, BIO.Project) in graph:
        return project_uri
    
    # Add type assertion
    graph.add((project_uri, RDF.type, BIO.Project))
    graph.add((project_uri, RDF.type, OWL.NamedIndividual))
    
    # Add data property
    graph.add((project_uri, BIO.projectId, Literal(project_id, datatype=XSD.string)))
    
    if verbose:
        print(f"  Added Project: {project_id}")
    
    return project_uri


def add_case_individual(
    graph: Graph, 
    case_data: Dict[str, Any], 
    project_uri: URIRef,
    verbose: bool = False
) -> URIRef:
    """Add a Case individual to the graph."""
    case_props = case_data.get('case_properties', {})
    case_id = case_props.get('bio:caseId')
    
    # If case_id not in properties, extract from IRI
    if not case_id:
        case_iri = case_data.get('individual_iri', '')
        case_id = case_iri.split('/')[-1] if case_iri else None
    
    if not case_id:
        return None
    
    case_uri = BIO[f"case/{case_id}"]
    
    # Check if already exists (avoid duplicates)
    if (case_uri, RDF.type, BIO.Case) in graph:
        # Still add the project relationship if needed
        graph.add((case_uri, BIO.caseInProject, project_uri))
        graph.add((project_uri, BIO.hasCase, case_uri))
        return case_uri
    
    # Add type assertion
    graph.add((case_uri, RDF.type, BIO.Case))
    graph.add((case_uri, RDF.type, OWL.NamedIndividual))
    
    # Add data properties
    graph.add((case_uri, BIO.caseId, Literal(case_id, datatype=XSD.string)))
    
    disease_type = case_props.get('bio:diseaseTypeLabel')
    if disease_type:
        graph.add((case_uri, BIO.diseaseTypeLabel, Literal(disease_type, datatype=XSD.string)))
    
    primary_site = case_props.get('bio:primarySiteLabel')
    if primary_site:
        graph.add((case_uri, BIO.primarySiteLabel, Literal(primary_site, datatype=XSD.string)))
    
    # Add object property: caseInProject
    graph.add((case_uri, BIO.caseInProject, project_uri))
    graph.add((project_uri, BIO.hasCase, case_uri))
    
    if verbose:
        print(f"  Added Case: {case_id}")
    
    return case_uri


def add_expression_measurement_individual(
    graph: Graph,
    expr_data: Dict[str, Any],
    gene_uri: URIRef,
    verbose: bool = False
) -> URIRef:
    """Add an ExpressionMeasurement individual to the graph."""
    expr_iri = expr_data.get('individual_iri', '')
    expr_id = expr_iri.split('/')[-1] if expr_iri else ''
    
    expr_uri = BIO[f"expression/{expr_id}"]
    
    # Add type assertion
    graph.add((expr_uri, RDF.type, BIO.ExpressionMeasurement))
    graph.add((expr_uri, RDF.type, OWL.NamedIndividual))
    
    # Add measurement data properties
    meas_props = expr_data.get('measurement_properties', {})
    
    file_id = meas_props.get('bio:fileId')
    if file_id:
        graph.add((expr_uri, BIO.fileId, Literal(file_id, datatype=XSD.string)))
    
    unstranded = meas_props.get('bio:unstrandedCount')
    if unstranded is not None:
        graph.add((expr_uri, BIO.unstrandedCount, Literal(Decimal(str(unstranded)), datatype=XSD.decimal)))
    
    stranded_first = meas_props.get('bio:strandedFirstCount')
    if stranded_first is not None:
        graph.add((expr_uri, BIO.strandedFirstCount, Literal(Decimal(str(stranded_first)), datatype=XSD.decimal)))
    
    stranded_second = meas_props.get('bio:strandedSecondCount')
    if stranded_second is not None:
        graph.add((expr_uri, BIO.strandedSecondCount, Literal(Decimal(str(stranded_second)), datatype=XSD.decimal)))
    
    tpm = meas_props.get('bio:tpmUnstranded')
    if tpm is not None:
        graph.add((expr_uri, BIO.tpmUnstranded, Literal(Decimal(str(tpm)), datatype=XSD.decimal)))
    
    fpkm = meas_props.get('bio:fpkmUnstranded')
    if fpkm is not None:
        graph.add((expr_uri, BIO.fpkmUnstranded, Literal(Decimal(str(fpkm)), datatype=XSD.decimal)))
    
    fpkm_uq = meas_props.get('bio:fpkmUqUnstranded')
    if fpkm_uq is not None:
        graph.add((expr_uri, BIO.fpkmUqUnstranded, Literal(Decimal(str(fpkm_uq)), datatype=XSD.decimal)))
    
    # Add object property: measuredGene
    graph.add((expr_uri, BIO.measuredGene, gene_uri))
    graph.add((gene_uri, BIO.hasGeneMeasurement, expr_uri))
    
    # Add Project relationship
    project_data = expr_data.get('project', {})
    project_id = project_data.get('project_properties', {}).get('bio:projectId')
    if project_id:
        project_uri = add_project_individual(graph, project_id, verbose)
        graph.add((expr_uri, BIO.measuredProject, project_uri))
        graph.add((project_uri, BIO.hasProjectMeasurement, expr_uri))
    else:
        project_uri = None
    
    # Add Case relationship
    case_data = expr_data.get('case', {})
    if case_data and project_uri:
        case_uri = add_case_individual(graph, case_data, project_uri, verbose)
        if case_uri:
            graph.add((expr_uri, BIO.measuredCase, case_uri))
            graph.add((case_uri, BIO.hasCaseMeasurement, expr_uri))
    
    if verbose:
        print(f"  Added ExpressionMeasurement: {expr_id}")
    
    return expr_uri


def process_ontology_individual(
    graph: Graph, 
    individual: Dict[str, Any], 
    verbose: bool = False
) -> None:
    """Process a complete ontology individual from JSON and add to graph."""
    onto_ind = individual.get('ontology_individual', {})
    
    if not onto_ind:
        print("Warning: No ontology_individual found in JSON")
        return
    
    # Process Gene
    gene_props = onto_ind.get('gene_properties', {})
    gene_uri = add_gene_individual(graph, gene_props, verbose)
    
    # Process Protein Products
    for protein_data in onto_ind.get('protein_products', []):
        add_protein_individual(graph, protein_data, gene_uri, verbose)
    
    # Process Expression Measurements
    for expr_data in onto_ind.get('expression_measurements', []):
        add_expression_measurement_individual(graph, expr_data, gene_uri, verbose)


def load_json_files(file_paths: List[str]) -> List[Dict[str, Any]]:
    """Load and combine JSON data from multiple files."""
    all_individuals = []
    
    for file_path in file_paths:
        path = Path(file_path)
        if not path.exists():
            print(f"Warning: File not found: {file_path}")
            continue
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Handle both single object and array formats
        if isinstance(data, list):
            all_individuals.extend(data)
        else:
            all_individuals.append(data)
    
    return all_individuals


def detect_ontology_format(filepath: str) -> str:
    """Detect the format of an ontology file based on content."""
    with open(filepath, 'r', encoding='utf-8') as f:
        first_line = f.readline().strip()
    
    # RDF/XML starts with XML declaration or <rdf:RDF
    if first_line.startswith('<?xml') or first_line.startswith('<rdf:RDF'):
        return 'xml'
    # Turtle files typically start with @prefix or @base
    elif first_line.startswith('@prefix') or first_line.startswith('@base'):
        return 'turtle'
    # N3 is similar to Turtle
    elif first_line.startswith('#') or ':' in first_line:
        return 'turtle'
    else:
        # Default to xml for .owl files, turtle otherwise
        return 'xml' if filepath.endswith('.owl') else 'turtle'


def main():
    """Main entry point."""
    args = parse_args()
    
    # Load base ontology with auto-detected format
    print(f"Loading ontology from: {args.ontology}")
    graph = Graph()
    
    # Auto-detect format
    ont_format = detect_ontology_format(args.ontology)
    print(f"Detected format: {ont_format}")
    graph.parse(args.ontology, format=ont_format)
    
    # Bind namespaces
    graph.bind('bio', BIO)
    graph.bind('owl', OWL)
    graph.bind('xsd', XSD)
    
    initial_count = len(graph)
    print(f"Initial triple count: {initial_count}")
    
    # Load JSON files
    print(f"Loading JSON data from: {args.input}")
    individuals = load_json_files(args.input)
    print(f"Found {len(individuals)} individual(s) to process")
    
    # Process each individual
    for i, individual in enumerate(individuals, 1):
        if args.verbose:
            print(f"\nProcessing individual {i}/{len(individuals)}:")
        process_ontology_individual(graph, individual, args.verbose)
    
    final_count = len(graph)
    print(f"\nFinal triple count: {final_count}")
    print(f"Added {final_count - initial_count} new triples")
    
    # Save output
    print(f"Saving populated ontology to: {args.output}")
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    graph.serialize(destination=str(output_path), format=args.format)
    
    print("Done!")


if __name__ == '__main__':
    main()
