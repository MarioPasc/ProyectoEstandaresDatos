import json
import logging
import sys
from pathlib import Path
from rdflib import Graph, Namespace

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
TTL_PATH = ROOT_DIR / "data" / "rdf" / "biointegrate_data_overlay.ttl"
OUTPUT_HTML_PATH = ROOT_DIR / "data" / "rdf" / "biointegrate_graph.html"

def generate_visualization():
    if not TTL_PATH.exists():
        logger.error(f"TTL file not found at {TTL_PATH}")
        return

    logger.info(f"Loading TTL from {TTL_PATH}...")
    g = Graph()
    g.parse(str(TTL_PATH), format="turtle")

    nodes = []
    edges = []
    node_ids = set()

    # Helper to get a label for a node
    def get_label(term):
        s = str(term)
        if "#" in s:
            return s.split("#")[-1]
        if "/" in s:
            return s.split("/")[-1]
        return s

    # Helper to determine group/color based on URI
    def get_group(term):
        s = str(term)
        if "gene" in s: return "Gene"
        if "protein" in s: return "Protein"
        if "case" in s: return "Case"
        if "project" in s: return "Project"
        if "expression" in s: return "Measurement"
        return "Literal" if not s.startswith("http") else "Resource"

    logger.info("Processing triples...")
    for s, p, o in g:
        # Add Subject Node
        s_id = str(s)
        if s_id not in node_ids:
            nodes.append({
                "id": s_id, 
                "label": get_label(s), 
                "group": get_group(s),
                "title": s_id  # Tooltip
            })
            node_ids.add(s_id)

        # Add Object Node
        o_id = str(o)
        if o_id not in node_ids:
            group = "Literal"
            if str(o).startswith("http"):
                group = get_group(o)
            
            # Truncate long literals for display
            label = get_label(o)
            if len(label) > 20:
                label = label[:20] + "..."

            nodes.append({
                "id": o_id, 
                "label": label, 
                "group": group,
                "title": str(o)
            })
            node_ids.add(o_id)

        # Add Edge
        edges.append({
            "from": s_id,
            "to": o_id,
            "label": get_label(p),
            "arrows": "to",
            "font": {"align": "middle", "size": 10}
        })

    logger.info(f"Graph contains {len(nodes)} nodes and {len(edges)} edges.")

    # HTML Template with vis.js
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>BioIntegrate RDF Graph</title>
        <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
        <style type="text/css">
            #mynetwork {{
                width: 100%;
                height: 90vh;
                border: 1px solid lightgray;
            }}
            body {{ font-family: sans-serif; }}
        </style>
    </head>
    <body>
        <h2>BioIntegrate RDF Data Overlay</h2>
        <div id="mynetwork"></div>
        <script type="text/javascript">
            var nodes = new vis.DataSet({json.dumps(nodes)});
            var edges = new vis.DataSet({json.dumps(edges)});

            var container = document.getElementById('mynetwork');
            var data = {{
                nodes: nodes,
                edges: edges
            }};
            var options = {{
                nodes: {{
                    shape: 'dot',
                    size: 16,
                    font: {{ size: 14 }}
                }},
                edges: {{
                    color: 'lightgray',
                    smooth: {{ type: 'continuous' }}
                }},
                groups: {{
                    Gene: {{ color: '#FF9999', shape: 'ellipse' }},
                    Protein: {{ color: '#99FF99', shape: 'ellipse' }},
                    Case: {{ color: '#9999FF', shape: 'box' }},
                    Project: {{ color: '#FFFF99', shape: 'database' }},
                    Measurement: {{ color: '#FFCC99', shape: 'dot', size: 10 }},
                    Literal: {{ color: '#EEEEEE', shape: 'text', font: {{ color: '#666666' }} }}
                }},
                physics: {{
                    stabilization: false,
                    barnesHut: {{
                        gravitationalConstant: -8000,
                        springConstant: 0.04,
                        springLength: 95
                    }}
                }}
            }};
            var network = new vis.Network(container, data, options);
        </script>
    </body>
    </html>
    """

    with open(OUTPUT_HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    logger.info(f"Visualization saved to: {OUTPUT_HTML_PATH}")

if __name__ == "__main__":
    generate_visualization()
