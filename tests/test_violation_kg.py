import os
import unittest
from rdflib import Graph, URIRef, Literal
from rdflib.namespace import RDF
import sys, os, unittest, json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from xshacl_architecture import ExplanationOutput
from violation_kg import ViolationKnowledgeGraph, XSH
from violation_signature import ViolationSignature
from unittest.mock import patch, mock_open


class TestViolationKnowledgeGraph(unittest.TestCase):
    @patch("builtins.open", new_callable=mock_open)
    @patch("rdflib.Graph.parse")
    def setUp(self, mock_parse, mock_file):
        # Mock the parse method to avoid file loading
        self.vkg = ViolationKnowledgeGraph(
            ontology_path="dummy_ontology.ttl", kg_path="dummy_kg.ttl"
        )
        # Clear the in-memory graph to start from an empty graph
        self.vkg.graph = Graph()

    def test_size_empty(self):
        self.vkg.clear()
        self.assertEqual(self.vkg.size(), 0, "Graph should be empty after clear()")

    def test_manual_add_triples(self):
        uri = URIRef("http://example.org/test")
        self.vkg.graph.add((uri, RDF.type, URIRef("http://example.org/Type")))
        self.vkg.graph.add(
            (uri, URIRef("http://example.org/predicate"), Literal("value1"))
        )
        self.vkg.graph.add(
            (uri, URIRef("http://example.org/predicate2"), Literal("value2"))
        )
        self.assertEqual(
            self.vkg.size(),
            3,
            "Graph should contain 3 triples after manual addition",
        )

    def test_add_violation_size(self):
        sig = ViolationSignature(
            constraint_id="test_constraint",
            property_path="test_property",
            violation_type="test_type",
            constraint_params={"key": "value"},
        )
        explanation = ExplanationOutput(
            natural_language_explanation="Test explanation",
            correction_suggestions=["Suggestion1", "Suggestion2"],
        )

        self.vkg.clear()
        self.vkg.add_violation(sig, explanation)
        self.assertEqual(
            self.vkg.size(),
            9,
            "Graph should contain 9 triples after adding a full violation explanation",
        )

    def test_has_violation(self):
        sig = ViolationSignature(
            constraint_id="test_constraint",
            property_path="test_property",
            violation_type="test_type",
            constraint_params={"key": "value"},
        )
        explanation = ExplanationOutput(
            natural_language_explanation="Test explanation",
            correction_suggestions=["Suggestion"],
        )

        self.vkg.clear()
        self.assertFalse(self.vkg.has_violation(sig))
        self.vkg.add_violation(sig, explanation)
        self.assertTrue(self.vkg.has_violation(sig))

    def test_get_explanation(self):
        sig = ViolationSignature(
            constraint_id="test_constraint",
            property_path="test_property",
            violation_type="test_type",
            constraint_params={"key": "value"},
        )
        original_explanation = ExplanationOutput(
            natural_language_explanation="Test explanation",
            correction_suggestions=["Suggestion"],
        )

        self.vkg.clear()
        self.vkg.add_violation(sig, original_explanation)

        retrieved_explanation = self.vkg.get_explanation(sig)
        self.assertEqual(
            retrieved_explanation.natural_language_explanation,
            original_explanation.natural_language_explanation,
        )
        self.assertEqual(
            retrieved_explanation.correction_suggestions,
            original_explanation.correction_suggestions,
        )

    def test_signature_to_uri(self):
        sig1 = ViolationSignature(
            constraint_id="test_constraint",
            property_path="test_property",
            violation_type="test_type",
            constraint_params={"key": "value"},
        )
        sig2 = ViolationSignature(
            constraint_id="different_constraint",
            property_path="different_property",
            violation_type="different_type",
            constraint_params={"different": "params"},
        )

        uri1 = self.vkg.signature_to_uri(sig1)
        uri2 = self.vkg.signature_to_uri(sig2)

        self.assertNotEqual(uri1, uri2)
        self.assertTrue(str(uri1).startswith(str(XSH)))
        self.assertTrue(str(uri2).startswith(str(XSH)))


if __name__ == "__main__":
    unittest.main()
