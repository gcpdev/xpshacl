import sys
import os
import unittest
from rdflib import Graph, URIRef, Literal
from rdflib.namespace import RDF, RDFS

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from xpshacl_architecture import ConstraintViolation, ShapeId, DomainContext
from context_retriever import ContextRetriever
from rdflib import Namespace


class TestContextRetriever(unittest.TestCase):

    def setUp(self):
        self.data_graph = Graph()
        self.shapes_graph = Graph()
        self.XSH = Namespace("http://xpshacl.org/#")

        # Add sample data to the data graph
        self.data_graph.add(
            (
                URIRef("http://example.org/node1"),
                RDF.type,
                URIRef("http://example.org/Type1"),
            )
        )
        self.data_graph.add(
            (
                URIRef("http://example.org/node1"),
                URIRef("http://example.org/hasName"),
                Literal("Node 1"),
            )
        )
        self.data_graph.add(
            (
                URIRef("http://example.org/node2"),
                RDF.type,
                URIRef("http://example.org/Type1"),
            )
        )

        # Add sample data to the shapes graph
        self.shapes_graph.add(
            (
                URIRef("http://example.org/shape1"),
                RDFS.comment,
                Literal("Shape 1 documentation"),
            )
        )
        self.shapes_graph.add(
            (
                URIRef("http://example.org/rule1"),
                self.XSH.appliesToProperty,
                URIRef("http://example.org/hasName"),
            )
        )
        self.shapes_graph.add(
            (
                URIRef("http://example.org/rule1"),
                RDFS.comment,
                Literal("Rule 1 description"),
            )
        )

        self.context_retriever = ContextRetriever(self.data_graph, self.shapes_graph)

    def test_get_ontology_fragments(self):
        violation = ConstraintViolation(
            focus_node="http://example.org/node1",
            property_path=None,
            constraint_id=None,
            shape_id="http://example.org/shape1",
            violation_type=None,
        )
        fragments = self.context_retriever._get_ontology_fragments(violation)
        expected_fragments = [
            "<http://example.org/node1> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://example.org/Type1>.",
            '<http://example.org/node1> <http://example.org/hasName> "Node 1".',
        ]
        self.assertEqual(fragments, expected_fragments)

    def test_get_shape_documentation(self):
        shape_id = ShapeId("http://example.org/shape1")
        documentation = self.context_retriever._get_shape_documentation(shape_id)
        expected_documentation = ["Shape 1 documentation"]
        self.assertEqual(documentation, expected_documentation)

    def test_get_similar_cases(self):
        violation = ConstraintViolation(
            focus_node="http://example.org/node1",
            property_path="http://example.org/hasName",
            constraint_id=None,
            shape_id="http://example.org/shape1",
            violation_type=None,
        )
        similar_cases = self.context_retriever._get_similar_cases(violation)
        expected_similar_cases = ["http://example.org/node2"]
        self.assertEqual(similar_cases, expected_similar_cases)

    def test_get_domain_rules(self):
        violation = ConstraintViolation(
            focus_node=None,
            property_path="http://example.org/hasName",
            constraint_id=None,
            shape_id="http://example.org/shape1",
            violation_type=None,
        )
        domain_rules = self.context_retriever._get_domain_rules(violation)
        expected_domain_rules = ["http://example.org/rule1: Rule 1 description"]
        self.assertEqual(domain_rules, expected_domain_rules)

    def test_retrieve_context(self):
        violation = ConstraintViolation(
            focus_node="http://example.org/node1",
            property_path="http://example.org/hasName",
            constraint_id=None,
            shape_id="http://example.org/shape1",
            violation_type=None,
        )
        context = self.context_retriever.retrieve_context(violation)

        expected_ontology_fragments = [
            "<http://example.org/node1> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://example.org/Type1>.",
            '<http://example.org/node1> <http://example.org/hasName> "Node 1".',
        ]
        expected_shape_documentation = ["Shape 1 documentation"]
        expected_similar_cases = ["http://example.org/node2"]
        expected_domain_rules = ["http://example.org/rule1: Rule 1 description"]

        self.assertEqual(context.ontology_fragments, expected_ontology_fragments)
        self.assertEqual(context.shape_documentation, expected_shape_documentation)
        self.assertEqual(context.similar_cases, expected_similar_cases)
        self.assertEqual(context.domain_rules, expected_domain_rules)


if __name__ == "__main__":
    unittest.main()
