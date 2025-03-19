import logging
from typing import Dict, List
from dataclasses import dataclass, field

from rdflib import Graph, URIRef, Namespace
from rdflib.namespace import RDFS, SH
from pyshacl import validate

from xshacl_architecture import (
    ConstraintViolation,
    ShapeId,
    DomainContext,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("xshacl")

# --- RAG Component for Context Retrieval ---


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
        for s, p, o in self.data_graph.triples(
            (URIRef(violation.focus_node), None, None)
        ):
            fragments.append(f"{s.n3()} {p.n3()} {o.n3()}.")
        return fragments

    def _get_shape_documentation(self, shape_id: ShapeId) -> List[str]:
        """Retrieves documentation associated with a shape"""
        documentation = []
        for s, p, o in self.shapes_graph.triples(
            (URIRef(shape_id), RDFS.comment, None)
        ):
            documentation.append(str(o))
        return documentation

    def _get_similar_cases(self, violation: ConstraintViolation) -> List[Dict]:
        """
        Finds 'similar cases' in the data graph. For example, if the violation is
        that a node doesn't have 'ex:hasName', we look for other nodes of the same type
        that are also missing 'ex:hasName'.

        Returns a list of URIs representing those similar nodes.
        """

        # 1. Identify the focus node type
        focus_node_uri = URIRef(violation.focus_node)
        property_path_uri = URIRef(violation.property_path) if violation.property_path else None

        # Query to find the type of the focus node:
        query_focus_type = f"""
        SELECT ?type
        WHERE {{
            <{focus_node_uri}> a ?type .
        }}
        """
        results_type = self.data_graph.query(query_focus_type)
        focus_node_types = [str(row["type"]) for row in results_type]

        # 2. For each focus_node_type, find other nodes of the same type
        # that are also missing the same property.
        similar_nodes = set()
        for t in focus_node_types:
            query_similar = f"""
            SELECT DISTINCT ?node
            WHERE {{
                ?node a <{t}> .
                FILTER NOT EXISTS {{
                   ?node <{property_path_uri}> ?anyval .
                }}
                FILTER(?node != <{focus_node_uri}>)
            }}
            """
            results_similar = self.data_graph.query(query_similar)
            for row in results_similar:
                similar_nodes.add(str(row["node"]))

        return list(similar_nodes)

    def _get_domain_rules(self, violation: ConstraintViolation) -> list[str]:
        """
        Returns a list of human-readable strings describing 'domain rules'
        that relate to the property path or constraint type for the given violation.
        """

        property_uri = violation.property_path
        constraint_id = violation.constraint_id

        if not property_uri:
            return []

        XSH = Namespace("http://xshacl.org/#")

        query = f"""
        PREFIX rdfs: <{RDFS}>
        PREFIX xsh: <http://xshacl.org/#>
        PREFIX sh: <{SH}>

        SELECT DISTINCT ?rule ?comment
        WHERE {{
            ?rule xsh:appliesToProperty <{property_uri}> .
            OPTIONAL {{ ?rule rdfs:comment ?comment . }}
        }}
        """

        results = self.shapes_graph.query(query)

        domain_rules = []
        for row in results:
            rule_uri_str = str(row["rule"])
            comment_str = str(row["comment"]) if row["comment"] else None
            if comment_str:
                domain_rules.append(f"{rule_uri_str}: {comment_str}")
            else:
                domain_rules.append(rule_uri_str)

        return domain_rules
