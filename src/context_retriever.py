import logging
from typing import Dict, List
from dataclasses import dataclass, field

from rdflib import Graph, URIRef, Namespace, Literal
from rdflib.namespace import RDFS, SH

# Assuming these are defined correctly in xpshacl_architecture
from xpshacl_architecture import (
    ConstraintViolation,
    ShapeId,
    DomainContext,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("xpshacl")


class ContextRetriever:
    """Retrieves relevant domain context for explaining a violation"""

    def __init__(self, data_graph: Graph, shapes_graph: Graph):
        self.data_graph = data_graph
        self.shapes_graph = shapes_graph

    def retrieve_context(self, violation: ConstraintViolation) -> DomainContext:
        """Retrieves domain context relevant to a constraint violation"""
        context = DomainContext()

        context.ontology_fragments = self._get_ontology_fragments(violation)
        context.shape_documentation = self._get_shape_documentation(violation.shape_id)
        context.similar_cases = self._get_similar_cases(violation)
        context.domain_rules = self._get_domain_rules(violation)

        return context

    def _get_ontology_fragments(self, violation: ConstraintViolation) -> List[str]:
        """Retrieves relevant ontology fragments based on the violation"""
        fragments = []
        focus_uri = URIRef(violation.focus_node)
        for s, p, o in self.data_graph.triples((focus_uri, None, None)):
            # Format Literals correctly in N3
            if isinstance(o, Literal):
                 # Handle Literals with specific arguments for n3()
                 o_n3 = o.n3() if hasattr(o, 'n3') else f'"{str(o)}"'
            elif hasattr(o, 'n3'): # Check if other types (URIRef, BNode) have n3()
                 o_n3 = o.n3()
            else:
                 # Handle unexpected types that cannot be serialized this way
                 print(f"Warning: Cannot serialize unexpected RDF term type: {type(o)} with value {o}")
                 o_n3 = f'"{str(o)}"'
            fragments.append(f"{s.n3()} {p.n3()} {o_n3} .")
        return fragments

    def _get_shape_documentation(self, shape_id: ShapeId) -> List[str]:
        """Retrieves documentation associated with a shape"""
        documentation = []
        shape_uri = URIRef(shape_id)
        for comment in self.shapes_graph.objects(shape_uri, RDFS.comment):
            documentation.append(str(comment))
        for name in self.shapes_graph.objects(shape_uri, SH.name):
             documentation.append(f"Shape Name: {str(name)}")
        return documentation

    def _get_similar_cases(self, violation: ConstraintViolation) -> List[Dict]:
        """
        Finds 'similar cases' in the data graph.
        Queries for nodes of the same type and checks for property absence in Python.

        Returns a list of dictionaries, each containing the URI ('node') and type ('node_type')
        of a similar node.
        """
        similar_nodes_data = []
        processed_nodes = set()

        # 1. Identify the focus node and property path
        focus_node_uri = URIRef(violation.focus_node)
        if violation.property_path is None:
             logger.debug("Cannot find similar cases without a property path in the violation.")
             return []
        property_path_uri = URIRef(violation.property_path)

        # 2. Find types of the focus node
        try:
            query_focus_type = "SELECT ?type WHERE { ?focus_node a ?type . }"
            results_type = self.data_graph.query(query_focus_type, initBindings={'focus_node': focus_node_uri})
            focus_node_types = {row["type"] for row in results_type if isinstance(row["type"], URIRef)}
            if not focus_node_types:
                 logger.warning(f"Could not determine RDF type for focus node {focus_node_uri}")
                 return []
        except Exception as e:
             logger.error(f"Error querying focus node type for {focus_node_uri}: {e}")
             return []

        # 3. For each type, query all nodes of that type and filter in Python
        for node_type_uri in focus_node_types:
            logger.debug(f"Searching for similar cases of type {node_type_uri} (Python filtering)")
            try:
                # Simpler query: Get all nodes of the specified type (excluding focus node)
                query_nodes_of_type = """
                SELECT ?node
                WHERE {
                    ?node a ?node_type .
                    FILTER(?node != ?focus_node)
                }
                """
                bindings = {'node_type': node_type_uri, 'focus_node': focus_node_uri}
                results_nodes = self.data_graph.query(query_nodes_of_type, initBindings=bindings)

                # Iterate through potential nodes and check property existence in Python
                for row in results_nodes:
                    node_uri = row["node"]
                    # Ensure we're dealing with a valid URI and haven't processed it
                    if isinstance(node_uri, URIRef):
                        node_uri_str = str(node_uri)
                        if node_uri_str not in processed_nodes:
                            # Check if the property exists for this node
                            # Using next() is slightly more efficient than checking len(list(...))
                            property_exists = next(self.data_graph.objects(node_uri, property_path_uri), None)

                            if property_exists is None: # Property does NOT exist
                                similar_nodes_data.append({
                                    "node": node_uri_str,
                                    "node_type": str(node_type_uri)
                                })
                            processed_nodes.add(node_uri_str) # Mark as processed even if property exists

            except Exception as e:
                logger.error(f"Error processing similar nodes (Python filter) for type {node_type_uri}: {e}")

        logger.debug(f"Found {len(similar_nodes_data)} similar cases for violation at {focus_node_uri} (Python filtering)")
        return similar_nodes_data


    def _get_domain_rules(self, violation: ConstraintViolation) -> list[str]:
        """
        Returns a list of human-readable strings describing 'domain rules'
        that relate to the property path involved in the given violation.
        """
        domain_rules = []
        # Ensure property_path exists
        if not violation.property_path:
            logger.debug("Skipping domain rules lookup as no property path is available.")
            return []

        property_uri = URIRef(violation.property_path)
        XSH = Namespace("http://xpshacl.org/#") # Define namespace if not globally available

        try:
            query = """
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX xsh: <http://xpshacl.org/#>

            SELECT DISTINCT ?rule ?comment ?label
            WHERE {{
                ?rule xsh:appliesToProperty ?prop_uri .
                OPTIONAL {{ ?rule rdfs:comment ?comment . }}
                OPTIONAL {{ ?rule rdfs:label ?label . }}
            }}
            """
            results = self.shapes_graph.query(query, initBindings={'prop_uri': property_uri})

            for row in results:
                rule_uri_str = str(row["rule"])
                label_str = str(row["label"]) if row["label"] else None
                comment_str = str(row["comment"]) if row["comment"] else None

                # Construct a readable representation
                rule_text = f"Rule <{rule_uri_str}>"
                if label_str:
                    rule_text += f" ({label_str})"
                if comment_str:
                    rule_text += f": {comment_str}"
                elif not label_str: # Fallback if only URI is present
                     rule_text += ": Applies to this property."

                domain_rules.append(rule_text)

        except Exception as e:
             logger.error(f"Error querying domain rules for property {property_uri}: {e}")

        logger.debug(f"Found {len(domain_rules)} domain rules for property {property_uri}")
        return domain_rules
