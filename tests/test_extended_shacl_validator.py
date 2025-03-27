import sys, os, unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import SH
from extended_shacl_validator import ExtendedShaclValidator
from xpshacl_architecture import ConstraintViolation, ViolationType

# language: python


class TestAddViolationContext(unittest.TestCase):
    def setUp(self):
        # Create a basic shapes graph and a dummy shape URI
        self.shapes_graph = Graph()
        self.shape_uri = URIRef("http://example.org/shape")
        # Create ExtendedShaclValidator with the shapes graph
        self.validator = ExtendedShaclValidator(self.shapes_graph)
        # Create a validation graph and a dummy result node
        self.validation_graph = Graph()
        self.result = URIRef("http://example.org/result")
        # Create a severity node with a fragment (e.g., Warning)
        self.severity_node = URIRef("http://www.w3.org/ns/shacl#Warning")
        self.validation_graph.add((self.result, SH.resultSeverity, self.severity_node))

    def test_add_min_count_context(self):
        # Add a minCount triple to the shapes graph
        self.shapes_graph.add((self.shape_uri, SH.minCount, Literal(3)))
        # Add an actual count triple to the validation graph
        self.validation_graph.add((self.result, SH.value, Literal(5)))
        # Create a CARDINALITY violation with a constraint_id containing "MinCountConstraintComponent"
        violation = ConstraintViolation(
            focus_node="dummy",
            shape_id=str(self.shape_uri),
            constraint_id=f"{self.shape_uri}#MinCountConstraintComponent",
            violation_type=ViolationType.CARDINALITY,
            property_path=None,
            value=None,
            message="Test minCount violation",
        )
        # Ensure context is initially empty
        violation.context = {}
        # Call _add_violation_context
        self.validator._add_violation_context(
            self.validation_graph, self.result, violation
        )
        # Assert that minCount and actualCount are set correctly
        self.assertIn("minCount", violation.context)
        self.assertEqual(violation.context["minCount"], 3)
        self.assertIn("actualCount", violation.context)
        self.assertEqual(violation.context["actualCount"], 5)
        # Assert severity is set from the severity node's fragment
        self.assertEqual(violation.severity, self.severity_node.fragment)

    def test_add_max_count_context(self):
        # Add a maxCount triple to the shapes graph
        self.shapes_graph.add((self.shape_uri, SH.maxCount, Literal(10)))
        # Add an actual count triple to the validation graph
        self.validation_graph.add((self.result, SH.value, Literal(7)))
        # Create a CARDINALITY violation with a constraint_id containing "MaxCountConstraintComponent"
        violation = ConstraintViolation(
            focus_node="dummy",
            shape_id=str(self.shape_uri),
            constraint_id=f"{self.shape_uri}#MaxCountConstraintComponent",
            violation_type=ViolationType.CARDINALITY,
            property_path=None,
            value=None,
            message="Test maxCount violation",
        )
        violation.context = {}
        # Call _add_violation_context
        self.validator._add_violation_context(
            self.validation_graph, self.result, violation
        )
        # Assert that maxCount and actualCount are set correctly
        self.assertIn("maxCount", violation.context)
        self.assertEqual(violation.context["maxCount"], 10)
        self.assertIn("actualCount", violation.context)
        self.assertEqual(violation.context["actualCount"], 7)
        # Assert severity is set
        self.assertEqual(violation.severity, self.severity_node.fragment)

    def test_actual_count_conversion_error(self):
        # Create a shapes graph entry for minCount even though count conversion should fail
        self.shapes_graph.add((self.shape_uri, SH.minCount, Literal(2)))
        # Add an invalid actual count value (non-integer) to the validation graph
        self.validation_graph.add((self.result, SH.value, Literal("non-integer")))
        # Create a CARDINALITY violation with minCount constraint identifier
        violation = ConstraintViolation(
            focus_node="dummy",
            shape_id=str(self.shape_uri),
            constraint_id=f"{self.shape_uri}#MinCountConstraintComponent",
            violation_type=ViolationType.CARDINALITY,
            property_path=None,
            value=None,
            message="Test count conversion failure",
        )
        violation.context = {}
        # Call _add_violation_context; conversion should fail and not add "actualCount"
        self.validator._add_violation_context(
            self.validation_graph, self.result, violation
        )
        self.assertIn("minCount", violation.context)
        self.assertEqual(violation.context["minCount"], 2)
        # "actualCount" should not be set due to conversion error
        self.assertNotIn("actualCount", violation.context)
        # Assert severity is set
        self.assertEqual(violation.severity, self.severity_node.fragment)

    def test_non_cardinality_violation(self):
        # For a violation type that is not CARDINALITY, context should remain unchanged except severity.
        violation = ConstraintViolation(
            focus_node="dummy",
            shape_id=str(self.shape_uri),
            constraint_id=f"{self.shape_uri}#SomeOtherConstraint",
            violation_type=ViolationType.VALUE_TYPE,
            property_path=None,
            value=None,
            message="Non-cardinality type",
        )
        violation.context = {"existing": "data"}
        # Add an actual count triple even though it should be ignored
        self.validation_graph.add((self.result, SH.value, Literal(100)))
        # Call _add_violation_context
        self.validator._add_violation_context(
            self.validation_graph, self.result, violation
        )
        # The context should not include minCount or maxCount or actualCount since violation type isn't CARDINALITY
        self.assertEqual(violation.context, {"existing": "data"})
        # Severity should still be set
        self.assertEqual(violation.severity, self.severity_node.fragment)


if __name__ == "__main__":
    unittest.main()
