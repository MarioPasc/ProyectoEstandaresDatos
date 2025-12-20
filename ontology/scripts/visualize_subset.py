from rdflib import Graph, Namespace, RDF
from pyvis.network import Network
from pathlib import Path

# 1. Rutas
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
TTL_FILE = ROOT_DIR / "data" / "rdf" / "export.ttl"
OUTPUT_HTML = ROOT_DIR / "data" / "rdf" / "visualizacion_limpia.html"
BI = Namespace("http://example.org/biointegrate/")

# 2. Cargar datos
g = Graph()
g.parse(str(TTL_FILE), format="turtle")

# 3. Configurar red (física mejorada para que no explote)
net = Network(height="800px", width="100%", bgcolor="#ffffff", font_color="#333333", directed=True)
net.force_atlas_2based() # Distribución más organizada

def add_styled_node(uri, label, color, size=20):
    net.add_node(str(uri), label=label, color=color, size=size, title=str(uri))

# 4. Lógica de Filtrado Inteligente
target_gene = BI["gene/HGNC_7539"] # MXRA5
add_styled_node(target_gene, "GEN: MXRA5", "#FFD700", 35) # ORO

print("Procesando ruta biológica y top mediciones...")

# RUTA 1: Biología (Gen -> Proteína -> GO)
for protein in g.objects(target_gene, BI.hasProteinProduct):
    prot_label = str(protein).split('/')[-1]
    add_styled_node(protein, f"PROT: {prot_label}", "#1E90FF", 30) # AZUL
    net.add_edge(str(target_gene), str(protein), label="produces")
    
    for go in g.objects(protein, BI.hasGoTerm):
        go_label = str(go).split('/')[-1]
        add_styled_node(go, f"GO: {go_label}", "#DA70D6") # ORQUÍDEA
        net.add_edge(str(protein), str(go), label="annotated_with")

# RUTA 2: Clínica (Solo las primeras 5 mediciones para no saturar)
count = 0
for meas in g.subjects(BI.measuredGene, target_gene):
    if count >= 5: break # LIMITAR AQUÍ EL RUIDO
    
    meas_label = "Medición_" + str(count+1)
    add_styled_node(meas, meas_label, "#32CD32", 15) # VERDE
    net.add_edge(str(meas), str(target_gene), label="of_gene")
    
    for case in g.objects(meas, BI.measuredCase):
        case_id = str(case).split('/')[-1][:8] + "..."
        add_styled_node(case, f"Caso: {case_id}", "#FF4500", 25) # ROJO
        net.add_edge(str(meas), str(case), label="in_case")
    
    count += 1

# 5. Guardar
net.show(str(OUTPUT_HTML), notebook=False)
print(f"✓ Visualización legible generada en: {OUTPUT_HTML}")