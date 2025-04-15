import sys
import os
import unittest
from rdflib import Graph, Literal, Namespace
from rdflib.namespace import RDF, RDFS, SH, XSD

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from xpshacl_architecture import ConstraintViolation, DomainContext
from context_retriever import ContextRetriever


EX = Namespace("http://example.org/")
XSH = Namespace("http://xpshacl.org/#")


class TestContextRetriever(unittest.TestCase):

    def setUp(self):
        self.data_graph = Graph()
        self.shapes_graph = Graph()

        self.node1 = EX.node1
        self.node2 = EX.node2
        self.node3 = EX.node3
        self.type1 = EX.Type1
        self.hasName = EX.hasName
        self.hasValue = EX.hasValue

        self.data_graph.add((self.node1, RDF.type, self.type1))
        self.data_graph.add((self.node1, self.hasName, Literal("Node 1")))
        self.data_graph.add((self.node1, self.hasValue, Literal(10)))

        self.data_graph.add((self.node2, RDF.type, self.type1))
        # node2 deliberately does NOT have hasName, making it "similar"

        self.data_graph.add((self.node3, RDF.type, self.type1))
        self.data_graph.add((self.node3, self.hasName, Literal("Node 3"))) # node3 has the property

        self.shape1 = EX.shape1
        self.rule1 = EX.rule1
        self.rule2 = EX.rule2

        self.shapes_graph.add((self.shape1, RDFS.comment, Literal("Shape 1 documentation")))
        self.shapes_graph.add((self.shape1, SH.name, Literal("ShapeOne"))) # Added SH.name

        self.shapes_graph.add((self.rule1, XSH.appliesToProperty, self.hasName))
        self.shapes_graph.add((self.rule1, RDFS.comment, Literal("Rule 1 description")))
        self.shapes_graph.add((self.rule1, RDFS.label, Literal("Rule One Label"))) # Added label

        self.shapes_graph.add((self.rule2, XSH.appliesToProperty, self.hasName))
        self.shapes_graph.add((self.rule2, RDFS.comment, Literal("Rule 2 description")))
        # Rule 2 has no label

        self.context_retriever = ContextRetriever(self.data_graph, self.shapes_graph)

    def test_get_ontology_fragments(self):
        violation = ConstraintViolation(
            focus_node=self.node1,
            property_path=self.hasName,
            constraint_id=None,
            shape_id=self.shape1,
            violation_type=None,
        )
        fragments = self.context_retriever._get_ontology_fragments(violation)
        expected_fragments = [
            f'<{self.node1}> <{RDF.type}> <{self.type1}> .',
            f'<{self.node1}> <{self.hasName}> "Node 1" .',
            f'<{self.node1}> <{self.hasValue}> "10"^^<{XSD.integer}> .',
        ]
        expected_fragments[2] = f'<{self.node1}> <{self.hasValue}> {Literal(10).n3()} .'

        self.assertCountEqual(fragments, expected_fragments)

    def test_get_shape_documentation(self):
        # Assuming violation.shape_id passes the URI/string correctly
        shape_uri_for_lookup = self.shape1
        documentation = self.context_retriever._get_shape_documentation(shape_uri_for_lookup)
        expected_documentation = [
            "Shape 1 documentation",
            "Shape Name: ShapeOne"
            ]
        self.assertCountEqual(documentation, expected_documentation)

    def test_get_similar_cases(self):
        violation = ConstraintViolation(
            focus_node=self.node1,
            property_path=self.hasName, 
            constraint_id=None,
            shape_id=self.shape1,
            violation_type=None,
        )
        similar_cases = self.context_retriever._get_similar_cases(violation)
        # Expect node2 because it's Type1 but lacks hasName
        # node3 is Type1 but HAS hasName, so it's excluded
        expected_similar_cases = [
            {"node": str(self.node2), "node_type": str(self.type1)}
            ]
        self.assertIsInstance(similar_cases, list)
        # Need to compare list of dictionaries
        self.assertEqual(len(similar_cases), len(expected_similar_cases))
        self.assertEqual(sorted(similar_cases, key=lambda x: x['node']), sorted(expected_similar_cases, key=lambda x: x['node']))


    def test_get_domain_rules(self):
        violation = ConstraintViolation(
            focus_node=self.node1,
            property_path=self.hasName,
            constraint_id=None,
            shape_id=self.shape1,
            violation_type=None,
        )
        domain_rules = self.context_retriever._get_domain_rules(violation)
        expected_domain_rules = [
             # Format: Rule <uri> (label): comment R Rule <uri>: comment
            f"Rule <{self.rule1}> (Rule One Label): Rule 1 description",
            f"Rule <{self.rule2}>: Rule 2 description",
        ]
        self.assertCountEqual(domain_rules, expected_domain_rules)

    def test_retrieve_context(self):
        violation = ConstraintViolation(
            focus_node=self.node1,
            property_path=self.hasName,
            constraint_id=None,
            shape_id=self.shape1,
            violation_type=None,
        )
        context = self.context_retriever.retrieve_context(violation)

        expected_ontology_fragments = [
            f'<{self.node1}> <{RDF.type}> <{self.type1}> .',
            f'<{self.node1}> <{self.hasName}> "Node 1" .',
            f'<{self.node1}> <{self.hasValue}> {Literal(10).n3()} .',
        ]
        expected_shape_documentation = [
             "Shape 1 documentation",
             "Shape Name: ShapeOne"
             ]
        expected_similar_cases = [
            {"node": str(self.node2), "node_type": str(self.type1)}
            ]
        expected_domain_rules = [
            f"Rule <{self.rule1}> (Rule One Label): Rule 1 description",
            f"Rule <{self.rule2}>: Rule 2 description",
        ]

        self.assertIsInstance(context, DomainContext)
        self.assertCountEqual(context.ontology_fragments, expected_ontology_fragments)
        self.assertCountEqual(context.shape_documentation, expected_shape_documentation)
        # Compare lists of dictionaries for similar_cases
        self.assertEqual(len(context.similar_cases), len(expected_similar_cases))
        self.assertEqual(sorted(context.similar_cases, key=lambda x: x['node']), sorted(expected_similar_cases, key=lambda x: x['node']))
        self.assertCountEqual(context.domain_rules, expected_domain_rules)


if __name__ == "__main__":
    unittest.main()