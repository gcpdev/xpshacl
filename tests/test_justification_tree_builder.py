from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF, RDFS, SH
import sys, os, unittest, json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from justification_tree_builder import JustificationTreeBuilder
from xshacl_architecture import (
    ConstraintViolation,
    ViolationType,
)


EX = Namespace("http://xshacl.org/#")


class DummyViolation(ConstraintViolation):
    def __init__(
        self,
        focus_node,
        value,
        constraint_id,
        shape_id,
        severity,
        message,
        violation_type,
        property_path=None,
        context=None,
    ):
        self.focus_node = focus_node
        self.value = value
        self.constraint_id = constraint_id
        self.shape_id = shape_id
        self.severity = severity
        self.message = message
        self.violation_type = violation_type
        self.property_path = property_path
        self.context = context or {}


class TestJustificationTreeBuilder(unittest.TestCase):
    def setUp(self):
        self.data_graph = Graph()
        self.shapes_graph = Graph()
        # Optionally bind a prefix for clarity in tests
        self.data_graph.bind("ex", EX)
        self.shapes_graph.bind("ex", EX)
        self.builder = JustificationTreeBuilder(self.data_graph, self.shapes_graph)

    def test_generic_justification(self):
        violation = DummyViolation(
            focus_node=str(EX.node1),
            value="dummy",
            constraint_id=str(EX.constraint),
            shape_id=str(EX.shape),
            severity="violation",
            message="Test generic violation",
            violation_type="unknown",
            property_path=str(EX.prop),
        )
        tree = self.builder.build_justification_tree(violation)
        # The generic justification should add a child node with type 'unknown'
        unknown_nodes = [
            child for child in tree.root.children if child.type == "unknown"
        ]
        self.assertTrue(len(unknown_nodes) >= 1)
        self.assertIn("Test generic violation", unknown_nodes[0].statement)

    def test_cardinality_min(self):
        # Simulate a cardinality violation for minimum count
        violation = DummyViolation(
            focus_node=str(EX.node1),
            value="dummy",
            constraint_id="MinCountConstraintComponent",
            shape_id=str(EX.shape),
            severity="violation",
            message="Cardinality min violation",
            violation_type=ViolationType.CARDINALITY,
            property_path=str(EX.prop),
            context={"minCount": 2, "actualCount": 1},
        )
        tree = self.builder.build_justification_tree(violation)
        # Check that the observation and inference nodes related to cardinality exist
        obs_nodes = [
            child for child in tree.root.children if child.type == "observation"
        ]
        inf_nodes = [child for child in tree.root.children if child.type == "inference"]
        self.assertTrue(any("has 1 values" in node.statement for node in obs_nodes))
        self.assertTrue(any("1 < at least 2" in node.statement for node in inf_nodes))

    def test_value_type_class(self):
        # Simulate a value type violation where the node is not an instance of the required class
        violation = DummyViolation(
            focus_node=str(EX.node2),
            value=None,
            constraint_id="ClassConstraintComponent",
            shape_id=str(EX.shape),
            severity="violation",
            message="Value type violation",
            violation_type=ViolationType.VALUE_TYPE,
            property_path=str(EX.prop),
        )
        tree = self.builder.build_justification_tree(violation)
        obs_nodes = [
            child for child in tree.root.children if child.type == "observation"
        ]
        # In this case the observation should mention that the node is not an instance.
        self.assertTrue(
            any("is not an instance" in node.statement for node in obs_nodes)
        )

    def test_value_range(self):
        # Add a triple in shapes_graph for a minInclusive constraint
        self.shapes_graph.add((URIRef(EX.shape), SH.minInclusive, Literal(5)))
        violation = DummyViolation(
            focus_node=str(EX.node3),
            value=Literal(3),
            constraint_id="MinInclusiveConstraintComponent",
            shape_id=str(EX.shape),
            severity="violation",
            message="Value range violation",
            violation_type=ViolationType.VALUE_RANGE,
            property_path=str(EX.prop),
        )
        tree = self.builder.build_justification_tree(violation)
        inf_nodes = [child for child in tree.root.children if child.type == "inference"]
        self.assertTrue(
            any("5" in node.statement for node in inf_nodes),
            "Expected minInclusive value in inference",
        )

    def test_pattern(self):
        # Add a triple in shapes_graph for a pattern constraint
        pattern_value = "^[A-Z]+$"
        self.shapes_graph.add((URIRef(EX.shape), SH.pattern, Literal(pattern_value)))
        # Optionally add flags
        self.shapes_graph.add((URIRef(EX.shape), SH.flags, Literal("i")))
        violation = DummyViolation(
            focus_node=str(EX.node4),
            value="abc",  # does not match the pattern
            constraint_id="PatternConstraintComponent",
            shape_id=str(EX.shape),
            severity="violation",
            message="Pattern violation",
            violation_type=ViolationType.PATTERN,
            property_path=str(EX.prop),
        )
        tree = self.builder.build_justification_tree(violation)
        inf_nodes = [child for child in tree.root.children if child.type == "inference"]
        self.assertTrue(
            any(pattern_value in node.statement for node in inf_nodes),
            "Expected pattern in inference",
        )
        self.assertTrue(
            any("i" in node.statement for node in inf_nodes),
            "Expected flags in inference",
        )

    def test_logical(self):
        # Add a triple to simulate a 'not' logical constraint in shapes_graph
        self.shapes_graph.add(
            (URIRef(EX.shape), SH.NotConstraintComponent, URIRef(EX.notshape))
        )
        violation = DummyViolation(
            focus_node=str(EX.node5),
            value="dummy",
            constraint_id="NotConstraintComponent",
            shape_id=str(EX.shape),
            severity="violation",
            message="Logical violation",
            violation_type=ViolationType.LOGICAL,
            property_path=str(EX.prop),
        )
        tree = self.builder.build_justification_tree(violation)
        inf_nodes = [child for child in tree.root.children if child.type == "inference"]
        # Check that the inference node mentions the negation of the notShape.
        self.assertTrue(
            any(str(EX.notshape) in node.statement for node in inf_nodes),
            "Expected not shape in inference",
        )


if __name__ == "__main__":
    unittest.main()
