"""
Justification Tree Builder
-------------------------
This module constructs logical justification trees for SHACL constraint violations.
These trees represent the formal reasoning behind a validation failure.
"""

import logging
from typing import Dict, Optional, List, Tuple, Set
from rdflib import Graph, URIRef, BNode, Literal, Namespace
from rdflib.namespace import RDF, RDFS, SH

from xshacl_architecture import (
    ConstraintViolation,
    JustificationNode,
    JustificationTree,
    ViolationType,
    NodeId,
    ConstraintId,
    ShapeId,
)

logger = logging.getLogger("xshacl.justification")

# Useful namespaces
SCHEMA = Namespace("http://schema.org/")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")


class JustificationTreeBuilder:
    """
    Constructs logical justification trees for SHACL constraint violations.
    """

    def __init__(self, data_graph: Graph, shapes_graph: Graph):
        """
        Initialize the justification tree builder.

        Args:
            data_graph: RDFLib Graph containing the data that was validated
            shapes_graph: RDFLib Graph containing the SHACL shapes used for validation
        """
        self.data_graph = data_graph
        self.shapes_graph = shapes_graph
        self._prefixes = self._collect_prefixes()

    def _collect_prefixes(self) -> Dict[str, str]:
        """Collect namespace prefixes from both graphs for nicer output"""
        prefixes = {}
        prefixes.update(dict(self.data_graph.namespaces()))
        prefixes.update(dict(self.shapes_graph.namespaces()))
        # Add default prefixes if not already present
        if "sh" not in prefixes:
            prefixes["sh"] = str(SH)
        if "rdf" not in prefixes:
            prefixes["rdf"] = str(RDF)
        if "rdfs" not in prefixes:
            prefixes["rdfs"] = str(RDFS)
        if "schema" not in prefixes:
            prefixes["schema"] = str(SCHEMA)
        if "foaf" not in prefixes:
            prefixes["foaf"] = str(FOAF)
        return prefixes

    def build_justification_tree(
        self, violation: ConstraintViolation
    ) -> JustificationTree:
        """
        Build a justification tree for a constraint violation.

        Args:
            violation: The constraint violation to explain

        Returns:
            A justification tree explaining the violation
        """
        # Create the root node of the justification tree
        root_statement = (
            f"Node {self._format_uri(violation.focus_node)} fails to conform to "
            f"shape {self._format_uri(violation.shape_id)}"
        )
        root = JustificationNode(statement=root_statement, type="conclusion")

        # Build the justification tree based on the violation type
        if violation.violation_type == ViolationType.CARDINALITY:
            self._build_cardinality_justification(violation, root)
        elif violation.violation_type == ViolationType.VALUE_TYPE:
            self._build_value_type_justification(violation, root)
        elif violation.violation_type == ViolationType.VALUE_RANGE:
            self._build_value_range_justification(violation, root)
        elif violation.violation_type == ViolationType.PATTERN:
            self._build_pattern_justification(violation, root)
        elif violation.violation_type == ViolationType.PROPERTY_PAIR:
            self._build_property_pair_justification(violation, root)
        elif violation.violation_type == ViolationType.LOGICAL:
            self._build_logical_justification(violation, root)
        else:
            self._build_generic_justification(violation, root)

        return JustificationTree(root=root, violation=violation)

    def _build_cardinality_justification(
        self, violation: ConstraintViolation, root: JustificationNode
    ) -> None:
        """Build justification for a cardinality constraint violation"""
        property_path = violation.property_path
        if not property_path:
            root.add_child(
                JustificationNode(
                    statement="Missing property path information for cardinality constraint",
                    type="error",
                )
            )
            return

        # Add shape requirement premise
        shape_constraint = self._get_shape_constraint_text(violation)
        root.add_child(
            JustificationNode(
                statement=shape_constraint,
                type="premise",
                evidence=f"From shape definition: {violation.shape_id}",
            )
        )

        # Add actual data observation
        if "MinCountConstraintComponent" in violation.constraint_id:
            min_count = violation.context.get("minCount", "at least 1")

            # Count actual values in the data
            actual_count = violation.context.get("actualCount")
            if actual_count is None:
                # If not available in context, compute it
                actual_count = self._count_property_values(
                    violation.focus_node, property_path
                )

            data_statement = (
                f"The data shows that node {self._format_uri(violation.focus_node)} "
                f"has {actual_count} values for property {self._format_uri(property_path)}"
            )
            count_node = JustificationNode(
                statement=data_statement,
                type="observation",
                evidence=self._generate_data_evidence(
                    violation.focus_node, property_path
                ),
            )
            root.add_child(count_node)

            # Add reasoning
            reasoning = (
                f"Since {actual_count} < {min_count}, the node violates the minimum cardinality "
                f"constraint of the shape"
            )
            root.add_child(JustificationNode(statement=reasoning, type="inference"))

        elif "MaxCountConstraintComponent" in violation.constraint_id:
            max_count = violation.context.get("maxCount", "at most 1")

            # Count actual values in the data
            actual_count = violation.context.get("actualCount")
            if actual_count is None:
                # If not available in context, compute it
                actual_count = self._count_property_values(
                    violation.focus_node, property_path
                )

            data_statement = (
                f"The data shows that node {self._format_uri(violation.focus_node)} "
                f"has {actual_count} values for property {self._format_uri(property_path)}"
            )
            count_node = JustificationNode(
                statement=data_statement,
                type="observation",
                evidence=self._generate_data_evidence(
                    violation.focus_node, property_path
                ),
            )
            root.add_child(count_node)

            # Add reasoning
            reasoning = (
                f"Since {actual_count} > {max_count}, the node violates the maximum cardinality "
                f"constraint of the shape"
            )
            root.add_child(JustificationNode(statement=reasoning, type="inference"))

    def _build_value_type_justification(
        self, violation: ConstraintViolation, root: JustificationNode
    ) -> None:
        """Build justification for a value type constraint violation"""
        property_path = violation.property_path
        if not property_path:
            property_path = "this node"  # For node shape type constraints

        # Add shape requirement premise
        shape_constraint = self._get_shape_constraint_text(violation)
        root.add_child(
            JustificationNode(
                statement=shape_constraint,
                type="premise",
                evidence=f"From shape definition: {violation.shape_id}",
            )
        )

        # Add actual data observation
        value = violation.value
        if not value and "ClassConstraintComponent" in violation.constraint_id:
            # For class constraints without a specific value, explain that the node itself has the wrong type
            data_statement = f"The node {self._format_uri(violation.focus_node)} is not an instance of the required class"
            evidence = self._generate_type_evidence(violation.focus_node)
        else:
            data_statement = (
                f"The value {self._format_uri(value)} for property {self._format_uri(property_path)} "
                f"of node {self._format_uri(violation.focus_node)} has an incompatible type"
            )
            evidence = self._generate_data_evidence(violation.focus_node, property_path)

        root.add_child(
            JustificationNode(
                statement=data_statement, type="observation", evidence=evidence
            )
        )

        # Add reasoning
        if "DatatypeConstraintComponent" in violation.constraint_id:
            datatype = None
            for s, p, o in self.shapes_graph.triples(
                (URIRef(violation.shape_id), SH.datatype, None)
            ):
                datatype = str(o)

            if datatype:
                reasoning = f"The value does not match the required datatype {self._format_uri(datatype)}"
                root.add_child(JustificationNode(statement=reasoning, type="inference"))
        elif "ClassConstraintComponent" in violation.constraint_id:
            required_class = None
            for s, p, o in self.shapes_graph.triples(
                (URIRef(violation.shape_id), SH.ClassConstraintComponent, None)
            ):
                required_class = str(o)

            if required_class:
                reasoning = f"The value is not an instance of the required class {self._format_uri(required_class)}"
                root.add_child(JustificationNode(statement=reasoning, type="inference"))

    def _build_value_range_justification(
        self, violation: ConstraintViolation, root: JustificationNode
    ) -> None:
        """Build justification for a value range constraint violation"""
        property_path = violation.property_path
        if not property_path:
            root.add_child(
                JustificationNode(
                    statement="Missing property path information for value range constraint",
                    type="error",
                )
            )
            return

        # Add shape requirement premise
        shape_constraint = self._get_shape_constraint_text(violation)
        root.add_child(
            JustificationNode(
                statement=shape_constraint,
                type="premise",
                evidence=f"From shape definition: {violation.shape_id}",
            )
        )

        # Add actual data observation
        value = violation.value
        data_statement = (
            f"The data shows that property {self._format_uri(property_path)} of node "
            f"{self._format_uri(violation.focus_node)} has value {value}"
        )
        root.add_child(
            JustificationNode(
                statement=data_statement,
                type="observation",
                evidence=self._generate_data_evidence(
                    violation.focus_node, property_path
                ),
            )
        )

        # Add specific reasoning based on the constraint type
        if "MinExclusiveConstraintComponent" in violation.constraint_id:
            min_value = None
            for s, p, o in self.shapes_graph.triples(
                (URIRef(violation.shape_id), SH.minExclusive, None)
            ):
                min_value = str(o)

            if min_value:
                reasoning = f"The value {value} is not greater than {min_value}"
                root.add_child(JustificationNode(statement=reasoning, type="inference"))
        elif "MinInclusiveConstraintComponent" in violation.constraint_id:
            min_value = None
