"""
biointegrate/t2/transform.py
Convierte listas de diccionarios JSON a XML compatible con XSLT.
"""
import logging
from typing import Any, List, Dict
from pathlib import Path
from lxml import etree # type: ignore

logger = logging.getLogger(__name__)

def _build_xml_node(parent: etree.Element, key: str, value: Any) -> None:
    """Función recursiva para mapear datos JSON a nodos XML."""
    
    # Limpiar clave para que sea un tag XML válido (sin espacios, etc.)
    safe_key = key.replace(" ", "_").replace(":", "_")
    if safe_key.startswith("_"): safe_key = safe_key[1:]

    # Caso 1: Valor Nulo
    if value is None:
        etree.SubElement(parent, safe_key).set("is_null", "true")
        return

    # Caso 2: Listas (Arrays)
    if isinstance(value, list):
        # Creamos un nodo contenedor con el nombre de la clave
        list_wrapper = etree.SubElement(parent, safe_key)
        # Decidimos nombre para los hijos (ej: genes -> gene, o item)
        child_tag = safe_key[:-1] if safe_key.endswith('s') else f"{safe_key}_item"
        
        for item in value:
            if isinstance(item, (dict, list)):
                # Si el hijo es complejo, creamos nodo y recursión
                complex_node = etree.SubElement(list_wrapper, child_tag)
                # Si es un dict, iteramos sus claves dentro del nodo hijo
                if isinstance(item, dict):
                    for k, v in item.items():
                        # Truco: llamar a _build con el nodo hijo como padre
                        # pero pasando k y v para crear sub-sub-elementos
                        # NO, espera. _build crea un subelemento.
                        # Mejor: llamar recursivamente sobre el contenido
                        _build_xml_node_inner(complex_node, k, v)
                elif isinstance(item, list):
                     _build_xml_node(list_wrapper, child_tag, item)
            else:
                # Si es primitivo (str, int)
                child = etree.SubElement(list_wrapper, child_tag)
                child.text = str(item)
        return

    # Caso 3: Diccionarios (Objetos)
    if isinstance(value, dict):
        obj_node = etree.SubElement(parent, safe_key)
        for k, v in value.items():
            _build_xml_node(obj_node, k, v)
        return

    # Caso 4: Primitivos
    child = etree.SubElement(parent, safe_key)
    child.text = str(value)

def _build_xml_node_inner(parent: etree.Element, key: str, value: Any):
    """Auxiliar para procesar items dentro de listas de objetos."""
    safe_key = key.replace(" ", "_").replace(":", "_")
    if safe_key.startswith("_"): safe_key = safe_key[1:]
    
    if value is None:
        etree.SubElement(parent, safe_key).set("is_null", "true")
    elif isinstance(value, list):
        list_wrapper = etree.SubElement(parent, safe_key)
        child_tag = safe_key[:-1] if safe_key.endswith('s') else f"{safe_key}_item"
        for item in value:
            if isinstance(item, dict):
                complex_node = etree.SubElement(list_wrapper, child_tag)
                for k, v in item.items():
                    _build_xml_node_inner(complex_node, k, v)
            else:
                child = etree.SubElement(list_wrapper, child_tag)
                child.text = str(item)
    elif isinstance(value, dict):
        obj_node = etree.SubElement(parent, safe_key)
        for k, v in value.items():
            _build_xml_node_inner(obj_node, k, v)
    else:
        child = etree.SubElement(parent, safe_key)
        child.text = str(value)

def json_to_xml(data: List[Dict[str, Any]], root_tag: str = "results") -> etree.ElementTree:
    """Convierte una lista de resultados JSON a un árbol XML."""
    root = etree.Element(root_tag)
    
    for doc in data:
        # Cada documento raíz es un <result>
        result_node = etree.SubElement(root, "result")
        for k, v in doc.items():
            _build_xml_node_inner(result_node, k, v)
            
    return etree.ElementTree(root)

def save_xml(tree: etree.ElementTree, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(str(output_path), pretty_print=True, xml_declaration=True, encoding="UTF-8")

def apply_xslt(xml_path: Path, xslt_path: Path, html_output_path: Path) -> None:
    if not xml_path.exists(): raise FileNotFoundError(f"XML not found: {xml_path}")
    if not xslt_path.exists(): raise FileNotFoundError(f"XSLT not found: {xslt_path}")

    xml_doc = etree.parse(str(xml_path))
    xslt_doc = etree.parse(str(xslt_path))
    transform = etree.XSLT(xslt_doc)
    
    html_dom = transform(xml_doc)
    
    html_output_path.parent.mkdir(parents=True, exist_ok=True)
    html_dom.write(str(html_output_path), pretty_print=True, method="html", encoding="UTF-8")