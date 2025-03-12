"""
Extended SHACL Validator
-----------------------
This module extends a standard SHACL validator to capture detailed information
about constraint violations for building explanations.
"""

import re
from typing import List, Optional, Tuple
import logging
from rdflib import Graph, URIRef, Namespace
from rdflib.namespace import RDF, RDFS, SH
from pyshacl import validate

from xshacl_architecture import (
    ConstraintViolation,
    ViolationType,
)

logger = logging.getLogger("xshacl.validator")

# Define some useful SHACL namespaces
SH = Namespace("http://www.w3.org/ns/shacl#")


class ExtendedShaclValidator:
    """
    Extended SHACL validator that captures detailed information about constraint violations.
    """

    def __init__(self, shapes_graph: Graph, inference: str = "none"):
        """
        Initialize the extended SHACL validator.

        Args:
            shapes_graph: RDFLib Graph containing SHACL shapes
            inference: Inference option for the validator ('none', 'rdfs', 'owlrl', etc.)
        """
        self.shapes_graph = shapes_graph
        self.inference = inference
        self._shape_cache = {}  # Cache of shape information
        self._constraint_cache = {}  # Cache of constraint information
        self._initialize_caches()

    def _initialize_caches(self):
        """Pre-process shapes and constraints for faster lookup during explanation"""
        # Cache shape information
        for shape in self.shapes_graph.subjects(RDF.type, SH.NodeShape):
            self._cache_shape_info(shape)

        for shape in self.shapes_graph.subjects(RDF.type, SH.PropertyShape):
            self._cache_shape_info(shape)

    def _cache_shape_info(self, shape):
        """Cache information about a shape for faster lookup"""
        shape_id = str(shape)
        if shape_id in self._shape_cache:
            return

        # Basic shape information
        shape_info = {
            "id": shape_id,
            "type": (
                "NodeShape"
                if (shape, RDF.type, SH.NodeShape) in self.shapes_graph
                else "PropertyShape"
            ),
            "targets": [],
            "constraints": [],
            "property_path": None,
            "documentation": [],
        }

        # Get shape targets
        for p, o in self.shapes_graph.predicate_objects(shape):
            if p in (
                SH.targetClass,
                SH.targetNode,
                SH.targetSubjectsOf,
                SH.targetObjectsOf,
            ):
                shape_info["targets"].append((str(p), str(o)))
            elif p == SH.path:
                shape_info["property_path"] = str(o)
            elif p == RDFS.comment:
                shape_info["documentation"].append(str(o))

        # Cache constraint components
        constraint_predicates = {
            SH.minCount,
            SH.maxCount,
            SH.datatype,
            SH.__class__,
            SH.minExclusive,
            SH.minInclusive,
            SH.maxExclusive,
            SH.maxInclusive,
            SH.pattern,
            SH.flags,
            SH.equals,
            SH.disjoint,
            SH.lessThan,
            SH.lessThanOrEquals,
            SH.NotConstraintComponent,
            SH.AndConstraintComponent,
            SH.OrConstraintComponent,
            SH.xone,
        }

        for p, o in self.shapes_graph.predicate_objects(shape):
            if p in constraint_predicates:
                constraint_id = f"{shape_id}#{p.fragment}"
                self._constraint_cache[constraint_id] = {
                    "shape_id": shape_id,
                    "predicate": str(p),
                    "value": str(o),
                    "type": self._get_constraint_type(p),
                }
                shape_info["constraints"].append(constraint_id)

        self._shape_cache[shape_id] = shape_info

    def _get_constraint_type(self, predicate) -> ViolationType:
        """Map a SHACL constraint predicate to a violation type"""
        cardinality_constraints = {SH.minCount, SH.maxCount}
        value_type_constraints = {SH.datatype, SH.ClassConstraintComponent, SH.nodeKind}
        value_range_constraints = {
            SH.minExclusive,
            SH.minInclusive,
            SH.maxExclusive,
            SH.maxInclusive,
        }
        pattern_constraints = {SH.pattern}
        property_pair_constraints = {
            SH.equals,
            SH.disjoint,
            SH.lessThan,
            SH.lessThanOrEquals,
        }
        logical_constraints = {
            SH.NotConstraintComponent,
            SH.AndConstraintComponent,
            SH.OrConstraintComponent,
            SH.XoneConstraintComponent,
        }

        if predicate in cardinality_constraints:
            return ViolationType.CARDINALITY
        elif predicate in value_type_constraints:
            return ViolationType.VALUE_TYPE
        elif predicate in value_range_constraints:
            return ViolationType.VALUE_RANGE
        elif predicate in pattern_constraints:
            return ViolationType.PATTERN
        elif predicate in property_pair_constraints:
            return ViolationType.PROPERTY_PAIR
        elif predicate in logical_constraints:
            return ViolationType.LOGICAL
        else:
            return ViolationType.OTHER

    def validate(
        self, data_graph: Graph
    ) -> Tuple[bool, Graph, List[ConstraintViolation]]:
        """
        Validate a data graph against the shapes graph and extract detailed violation information.

        Args:
            data_graph: RDFLib Graph containing the data to validate

        Returns:
            Tuple of (is_valid, validation_report_graph, detailed_violations)
        """
        # Run standard validation
        is_valid, validation_graph, _ = validate(
            data_graph, shacl_graph=self.shapes_graph, inference=self.inference
        )

        # Extract detailed information about violations
        detailed_violations = self._extract_detailed_violations(validation_graph)

        return is_valid, validation_graph, detailed_violations

    def _extract_detailed_violations(
        self, validation_graph: Graph
    ) -> List[ConstraintViolation]:
        """Extract detailed violation information from the validation report graph"""
        detailed_violations = []

        # Find validation results in the report
        for result in validation_graph.subjects(RDF.type, SH.ValidationResult):
            violation = self._process_validation_result(validation_graph, result)
            if violation:
                detailed_violations.append(violation)

        return detailed_violations

    def _process_validation_result(
        self, validation_graph: Graph, result
    ) -> Optional[ConstraintViolation]:
        """Process a single validation result to extract detailed information"""
        try:
            # Extract required information
            focus_node = next(validation_graph.objects(result, SH.focusNode), None)
            if not focus_node:
                logger.warning(f"No focus node found for validation result {result}")
                return None

            source_shape = next(validation_graph.objects(result, SH.sourceShape), None)
            if not source_shape:
                logger.warning(f"No source shape found for validation result {result}")
                return None

            # Extract source constraint component
            source_constraint = next(
                validation_graph.objects(result, SH.sourceConstraintComponent), None
            )
            if not source_constraint:
                logger.warning(
                    f"No source constraint component found for validation result {result}"
                )
                return None

            # Extract path if available (for property shapes)
            path = next(validation_graph.objects(result, SH.resultPath), None)
            path_str = str(path) if path else None

            # Extract value that caused the violation
            value = next(validation_graph.objects(result, SH.value), None)
            value_str = str(value) if value else None

            # Extract validation message if available
            message = next(validation_graph.objects(result, SH.resultMessage), None)
            message_str = str(message) if message else None

            # Determine violation type
            violation_type = self._determine_violation_type(
                validation_graph, result, source_constraint
            )

            # Create constraint violation object
            violation = ConstraintViolation(
                focus_node=str(focus_node),
                shape_id=str(source_shape),
                constraint_id=str(source_constraint),
                violation_type=violation_type,
                property_path=path_str,
                value=value_str,
                message=message_str,
            )

            # Add additional context from the validation result
            self._add_violation_context(validation_graph, result, violation)

            return violation

        except Exception as e:
            logger.error(f"Error processing validation result {result}: {e}")
            return None

    def _determine_violation_type(
        self, validation_graph, result, source_constraint
    ) -> ViolationType:
        """Determine the type of violation based on the source constraint component"""
        constraint_str = str(source_constraint)

        # Use regular expressions to identify constraint types
        if re.search(r"(MinCount|MaxCount)Constraint", constraint_str):
            return ViolationType.CARDINALITY
        elif re.search(r"(Datatype|Class|NodeKind)Constraint", constraint_str):
            return ViolationType.VALUE_TYPE
        elif re.search(
            r"(MinExclusive|MinInclusive|MaxExclusive|MaxInclusive)Constraint",
            constraint_str,
        ):
            return ViolationType.VALUE_RANGE
        elif re.search(r"PatternConstraint", constraint_str):
            return ViolationType.PATTERN
        elif re.search(
            r"(Equals|Disjoint|LessThan|LessThanOrEquals)Constraint", constraint_str
        ):
            return ViolationType.PROPERTY_PAIR
        elif re.search(r"(Not|And|Or|Xone)Constraint", constraint_str):
            return ViolationType.LOGICAL
        else:
            return ViolationType.OTHER

    def _add_violation_context(
        self, validation_graph, result, violation: ConstraintViolation
    ) -> None:
        """Add additional context to the violation from the validation graph"""
        # Try to get constraint parameters (e.g., the actual min/max count values)
        if violation.violation_type == ViolationType.CARDINALITY:
            if "MinCountConstraintComponent" in violation.constraint_id:
                shape_id = violation.shape_id
                for s, p, o in self.shapes_graph.triples(
                    (URIRef(shape_id), SH.minCount, None)
                ):
                    violation.context["minCount"] = int(o)
            elif "MaxCountConstraintComponent" in violation.constraint_id:
                shape_id = violation.shape_id
                for s, p, o in self.shapes_graph.triples(
                    (URIRef(shape_id), SH.maxCount, None)
                ):
                    violation.context["maxCount"] = int(o)

        # Add severity information
        severity = next(validation_graph.objects(result, SH.resultSeverity), None)
        if severity:
            violation.severity = severity.fragment

        # Try getting actual count for cardinality violations
        if violation.violation_type == ViolationType.CARDINALITY:
            count = next(validation_graph.objects(result, SH.value), None)
            if count:
                try:
                    violation.context["actualCount"] = int(count)
                except (ValueError, TypeError):
                    pass
