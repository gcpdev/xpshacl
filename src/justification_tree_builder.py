"""
Justification Tree Builder
-------------------------
This module constructs logical justification trees for SHACL constraint violations.
These trees represent the formal reasoning behind a validation failure.
"""

import logging
from typing import Dict
from rdflib import Graph, URIRef, Namespace
from rdflib.namespace import RDF, RDFS, SH

from xpshacl_architecture import (
    ConstraintViolation,
    JustificationNode,
    JustificationTree,
    ViolationType,
    NodeId,
)

logger = logging.getLogger("xpshacl.justification")

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
                f"Since {actual_count} < at least {min_count}, the node violates the minimum cardinality "
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
                f"Since {actual_count} > at most {max_count}, the node violates the maximum cardinality "
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
                reasoning = f"The value provided does not comply with the minimum value restriction {min_value}"
                root.add_child(JustificationNode(statement=reasoning, type="inference"))
        elif "MinInclusiveConstraintComponent" in violation.constraint_id:
            min_value = None
            for s, p, o in self.shapes_graph.triples(
                (URIRef(violation.shape_id), SH.minInclusive, None)
            ):
                min_value = str(o)
            if min_value:
                reasoning = f"The value provided does not comply with the minimum value restriction {min_value}"
                root.add_child(JustificationNode(statement=reasoning, type="inference"))
        elif "MaxExclusiveConstraintComponent" in violation.constraint_id:
            max_value = None
            for s, p, o in self.shapes_graph.triples(
                (URIRef(violation.shape_id), SH.maxExclusive, None)
            ):
                max_value = str(o)

            if max_value:
                reasoning = f"The value provided does not comply with the maximum value restriction {max_value}"
                root.add_child(JustificationNode(statement=reasoning, type="inference"))

        elif "MaxInclusiveConstraintComponent" in violation.constraint_id:
            max_value = None
            for s, p, o in self.shapes_graph.triples(
                (URIRef(violation.shape_id), SH.maxInclusive, None)
            ):
                max_value = str(o)

            if max_value:
                reasoning = f"The value provided does not comply with the maximum value restriction {max_value}"
                root.add_child(JustificationNode(statement=reasoning, type="inference"))

    def _build_pattern_justification(
        self, violation: ConstraintViolation, root: JustificationNode
    ) -> None:
        """Build justification for a pattern constraint violation"""
        # Add shape requirement premise
        shape_constraint = self._get_shape_constraint_text(violation)
        root.add_child(
            JustificationNode(
                statement=shape_constraint,
                type="premise",
                evidence=f"From shape definition: {violation.shape_id}",
            )
        )

        # Extract values if possible
        focus_node = violation.focus_node
        property_path = violation.property_path
        value = violation.value
        pattern = ""

        # Add actual data observation
        if property_path and value:
            data_statement = f"The data shows that node {self._format_uri(focus_node)} has value {value} for property {self._format_uri(property_path)}."

            root.add_child(
                JustificationNode(
                    statement=data_statement,
                    type="observation",
                    evidence=self._generate_data_evidence(focus_node, property_path),
                )
            )
        # Add specific reasoning based on the constraint type
        if "PatternConstraintComponent" in violation.constraint_id:
            for s, p, o in self.shapes_graph.triples(
                (URIRef(violation.shape_id), SH.pattern, None)
            ):
                pattern = str(o)
            if pattern:
                reasoning = (
                    f"The value provided does not comply with the pattern {pattern}."
                )
                root.add_child(JustificationNode(statement=reasoning, type="inference"))

            # Add flag information if present
            flags = None
            for s, p, o in self.shapes_graph.triples(
                (URIRef(violation.shape_id), SH.flags, None)
            ):
                flags = str(o)
            if flags:
                reasoning = f"The pattern uses flags {flags}."
                root.add_child(JustificationNode(statement=reasoning, type="inference"))

    def _build_property_pair_justification(
        self, violation: ConstraintViolation, root: JustificationNode
    ) -> None:
        """Build justification for a property pair constraint violation"""
        # Add shape requirement premise
        shape_constraint = self._get_shape_constraint_text(violation)
        root.add_child(
            JustificationNode(
                statement=shape_constraint,
                type="premise",
                evidence=f"From shape definition: {violation.shape_id}",
            )
        )

        # Extract values if possible
        focus_node = violation.focus_node
        property_path = violation.property_path
        value = violation.value

        # Add actual data observation
        if property_path and value:
            data_statement = f"The data shows that node {self._format_uri(focus_node)} has value {value} for property {self._format_uri(property_path)}."

            root.add_child(
                JustificationNode(
                    statement=data_statement,
                    type="observation",
                    evidence=self._generate_data_evidence(focus_node, property_path),
                )
            )

        if "EqualsConstraintComponent" in violation.constraint_id:
            equals_property = None
            for s, p, o in self.shapes_graph.triples(
                (URIRef(violation.shape_id), SH.equals, None)
            ):
                equals_property = str(o)
            if equals_property:
                reasoning = f"The shape states that property {self._format_uri(property_path)} must have the same values as {self._format_uri(equals_property)}."
                root.add_child(JustificationNode(statement=reasoning, type="inference"))

        elif "DisjointConstraintComponent" in violation.constraint_id:
            disjoint_property = None
            for s, p, o in self.shapes_graph.triples(
                (URIRef(violation.shape_id), SH.disjoint, None)
            ):
                disjoint_property = str(o)
            if disjoint_property:
                reasoning = f"The shape states that property {self._format_uri(property_path)} must not have any of the same values as {self._format_uri(disjoint_property)}."
                root.add_child(JustificationNode(statement=reasoning, type="inference"))

        elif "LessThanConstraintComponent" in violation.constraint_id:
            less_than_property = None
            for s, p, o in self.shapes_graph.triples(
                (URIRef(violation.shape_id), SH.lessThan, None)
            ):
                less_than_property = str(o)

            if less_than_property:
                # Retrieve all the values related to the two properties
                less_than_values = [
                    str(o)
                    for s, p, o in self.data_graph.triples(
                        (URIRef(focus_node), URIRef(less_than_property), None)
                    )
                ]

                if len(less_than_values) > 0:
                    reasoning = f"The shape states that the value of property {self._format_uri(property_path)} must be less than the values {less_than_values} of {self._format_uri(less_than_property)}."
                else:
                    reasoning = f"The shape states that the value of property {self._format_uri(property_path)} must be less than the value of {self._format_uri(less_than_property)} but no value was found for {self._format_uri(less_than_property)}."
                root.add_child(JustificationNode(statement=reasoning, type="inference"))

        elif "LessThanOrEqualsConstraintComponent" in violation.constraint_id:
            less_or_equals_property = None
            for s, p, o in self.shapes_graph.triples(
                (URIRef(violation.shape_id), SH.lessThanOrEquals, None)
            ):
                less_or_equals_property = str(o)

            if less_or_equals_property:
                # Retrieve all the values related to the two properties
                less_than_or_equals_values = [
                    str(o)
                    for s, p, o in self.data_graph.triples(
                        (URIRef(focus_node), URIRef(less_or_equals_property), None)
                    )
                ]

                if len(less_than_or_equals_values) > 0:
                    reasoning = f"The shape states that the value of property {self._format_uri(property_path)} must be less than or equals to the values {less_than_or_equals_values} of {self._format_uri(less_or_equals_property)}."
                else:
                    reasoning = f"The shape states that the value of property {self._format_uri(property_path)} must be less than or equals to the value of {self._format_uri(less_or_equals_property)} but no value was found for {self._format_uri(less_or_equals_property)}."
                root.add_child(JustificationNode(statement=reasoning, type="inference"))

    def _build_property_pair_justification(
        self, violation: ConstraintViolation, root: JustificationNode
    ) -> None:
        """Build justification for a property pair constraint violation"""
        # Add shape requirement premise
        shape_constraint = self._get_shape_constraint_text(violation)
        root.add_child(
            JustificationNode(
                statement=shape_constraint,
                type="premise",
                evidence=f"From shape definition: {violation.shape_id}",
            )
        )

        # Extract values if possible
        focus_node = violation.focus_node
        property_path = violation.property_path
        value = violation.value

        # Add actual data observation
        if property_path and value:
            data_statement = f"The data shows that node {self._format_uri(focus_node)} has value {value} for property {self._format_uri(property_path)}."

            root.add_child(
                JustificationNode(
                    statement=data_statement,
                    type="observation",
                    evidence=self._generate_data_evidence(focus_node, property_path),
                )
            )

        if "EqualsConstraintComponent" in violation.constraint_id:
            equals_property = None
            for s, p, o in self.shapes_graph.triples(
                (URIRef(violation.shape_id), SH.equals, None)
            ):
                equals_property = str(o)
            if equals_property:
                reasoning = f"The shape states that property {self._format_uri(property_path)} must have the same values as {self._format_uri(equals_property)}."
                root.add_child(JustificationNode(statement=reasoning, type="inference"))

        elif "DisjointConstraintComponent" in violation.constraint_id:
            disjoint_property = None
            for s, p, o in self.shapes_graph.triples(
                (URIRef(violation.shape_id), SH.disjoint, None)
            ):
                disjoint_property = str(o)
            if disjoint_property:
                reasoning = f"The shape states that property {self._format_uri(property_path)} must not have any of the same values as {self._format_uri(disjoint_property)}."
                root.add_child(JustificationNode(statement=reasoning, type="inference"))

        elif "LessThanConstraintComponent" in violation.constraint_id:
            less_than_property = None
            for s, p, o in self.shapes_graph.triples(
                (URIRef(violation.shape_id), SH.lessThan, None)
            ):
                less_than_property = str(o)
            if less_than_property:
                reasoning = f"The shape states that the value of property {self._format_uri(property_path)} must be less than the value of {self._format_uri(less_than_property)}."
                root.add_child(JustificationNode(statement=reasoning, type="inference"))

        elif "LessThanOrEqualsConstraintComponent" in violation.constraint_id:
            less_or_equals_property = None
            for s, p, o in self.shapes_graph.triples(
                (URIRef(violation.shape_id), SH.lessThanOrEquals, None)
            ):
                less_or_equals_property = str(o)

            if less_or_equals_property:
                reasoning = f"The shape states that the value of property {self._format_uri(property_path)} must be less than or equal to the value of {self._format_uri(less_or_equals_property)}."
                root.add_child(JustificationNode(statement=reasoning, type="inference"))

    def _build_logical_justification(
        self, violation: ConstraintViolation, root: JustificationNode
    ) -> None:
        """Build justification for a logical constraint violation"""
        # Add shape requirement premise
        shape_constraint = self._get_shape_constraint_text(violation)
        root.add_child(
            JustificationNode(
                statement=shape_constraint,
                type="premise",
                evidence=f"From shape definition: {violation.shape_id}",
            )
        )

        # Add specific reasoning based on the constraint type
        if "NotConstraintComponent" in violation.constraint_id:
            # Find the 'sh:not' shape that contains the nested violation
            for s, p, o in self.shapes_graph.triples(
                (URIRef(violation.shape_id), SH.NotConstraintComponent, None)
            ):
                not_shape_id = o

            reasoning = f"The shape {self._format_uri(violation.shape_id)} includes a negation of the shape {self._format_uri(not_shape_id)}. This means that, for the resource to be valid, it cannot comply with the rules of the shape {self._format_uri(not_shape_id)}"
            root.add_child(JustificationNode(statement=reasoning, type="inference"))

        elif "AndConstraintComponent" in violation.constraint_id:
            # Find the 'sh:and' shape that contains the list of shapes
            for s, p, o in self.shapes_graph.triples(
                (URIRef(violation.shape_id), SH.AndConstraintComponent, None)
            ):
                and_shape_list = o

            reasoning = f"The shape {self._format_uri(violation.shape_id)} includes a conjunction of the shapes listed in {self._format_uri(and_shape_list)}. This means that, for the resource to be valid, it must comply with all rules of the shapes listed in {self._format_uri(and_shape_list)}"
            root.add_child(JustificationNode(statement=reasoning, type="inference"))

        elif "OrConstraintComponent" in violation.constraint_id:
            # Find the 'sh:or' shape that contains the list of shapes
            for s, p, o in self.shapes_graph.triples(
                (URIRef(violation.shape_id), SH.OrConstraintComponent, None)
            ):
                or_shape_list = o

            reasoning = f"The shape {self._format_uri(violation.shape_id)} includes a disjunction of the shapes listed in {self._format_uri(or_shape_list)}. This means that, for the resource to be valid, it must comply with at least one of the shapes listed in {self._format_uri(or_shape_list)}"
            root.add_child(JustificationNode(statement=reasoning, type="inference"))

        elif "XoneConstraintComponent" in violation.constraint_id:
            # Find the 'sh:xone' shape that contains the list of shapes
            for s, p, o in self.shapes_graph.triples(
                (URIRef(violation.shape_id), SH.XoneConstraintComponent, None)
            ):
                xone_shape_list = o

            reasoning = f"The shape {self._format_uri(violation.shape_id)} includes an exclusive disjunction of the shapes listed in {self._format_uri(xone_shape_list)}. This means that, for the resource to be valid, it must comply with exactly one of the shapes listed in {self._format_uri(xone_shape_list)}"
            root.add_child(JustificationNode(statement=reasoning, type="inference"))

    def _build_generic_justification(
        self, violation: ConstraintViolation, root: JustificationNode
    ) -> None:
        """Build generic justification for an unknown violation type"""
        root.add_child(
            JustificationNode(
                statement=f"Generic justification for violation: {violation.message or 'Unknown violation'}",
                type="unknown",
                evidence=None,
            )
        )

    def _format_uri(self, uri: str) -> str:
        """
        Formats a URI for human-readable output.
        """
        # Simple formatting - can be improved with prefix mappings, etc.
        if uri.startswith("http://") or uri.startswith("https://"):
            return f"<{uri}>"
        return uri

    def _get_shape_constraint_text(self, violation: ConstraintViolation) -> str:
        """
        Retrieves the constraint text from the shapes graph.
        """
        constraint_node = URIRef(violation.constraint_id)
        shape_node = URIRef(violation.shape_id)

        # Try to get the constraint value
        constraint_value = None
        for s, p, o in self.shapes_graph.triples((shape_node, None, None)):
            if str(p) == str(constraint_node):
                constraint_value = o
                break

        if constraint_value:
            return f"The shape {self._format_uri(violation.shape_id)} has a constraint {self._format_uri(violation.constraint_id)} with value {constraint_value}."
        else:
            return f"The shape {self._format_uri(violation.shape_id)} has a constraint {self._format_uri(violation.constraint_id)}."

    def _count_property_values(self, focus_node: NodeId, property_path: str) -> int:
        """
        Counts the number of values for a given property path of a focus node.
        """
        count = 0
        focus_uri = URIRef(focus_node)
        property_uri = URIRef(property_path)

        for s, p, o in self.data_graph.triples((focus_uri, property_uri, None)):
            count += 1
        return count

    def _generate_data_evidence(self, focus_node: NodeId, property_path: str) -> str:
        """
        Generates evidence from the data graph for a given focus node and property path.
        """
        evidence = ""
        focus_uri = URIRef(focus_node)
        property_uri = URIRef(property_path)

        for s, p, o in self.data_graph.triples((focus_uri, property_uri, None)):
            evidence += f"{s.n3()} {p.n3()} {o.n3()} .\n"
        return evidence

    def _generate_type_evidence(self, focus_node: NodeId) -> str:
        """
        Generates evidence about the type of a focus node from the data graph.
        """
        evidence = ""
        focus_uri = URIRef(focus_node)

        for s, p, o in self.data_graph.triples((focus_uri, RDF.type, None)):
            evidence += f"{s.n3()} {p.n3()} {o.n3()} .\n"
        return evidence
