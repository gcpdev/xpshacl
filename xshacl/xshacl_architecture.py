"""
xSHACL - eXplainable SHACL Validation: A Hybrid Approach to Constraint Explanation
---------------------------------------------------------------------------
This implementation provides an extensible framework for generating human-friendly
explanations of SHACL validation failures, combining rule-based justification trees
with retrieval-augmented generation for natural language explanations.

Main Components:
1. Extended SHACL Validator - Captures detailed validation information
2. Justification Tree Builder - Constructs logical explanation trees
3. Context Retriever - Fetches relevant domain knowledge
4. Explanation Generator - Produces natural language explanations using LLM

Author: Gustavo Publio
Date: March 2025
"""

import os
import json
import logging
from typing import Dict, List, Optional, Set, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("xshacl")

# Type definitions
NodeId = str  # URI or blank node identifier
ConstraintId = str  # URI of a constraint component
ShapeId = str  # URI of a shape definition


class ViolationType(Enum):
    """Types of SHACL constraint violations"""

    CARDINALITY = "cardinality"  # minCount, maxCount
    VALUE_TYPE = "value_type"  # datatype, class
    VALUE_RANGE = "value_range"  # minExclusive, maxInclusive, etc.
    PATTERN = "pattern"  # pattern
    PROPERTY_PAIR = "property_pair"  # equals, disjoint, lessThan, etc.
    LOGICAL = "logical"  # and, or, not, xone
    OTHER = "other"  # other types


@dataclass
class ConstraintViolation:
    """Represents a SHACL constraint violation with detailed information"""

    focus_node: NodeId  # The node that failed validation
    shape_id: ShapeId  # The shape the node was validated against
    constraint_id: ConstraintId  # The specific constraint that failed
    violation_type: ViolationType  # Category of violation
    property_path: Optional[str] = None  # Property path if applicable
    value: Optional[str] = None  # Value that violated the constraint
    message: Optional[str] = None  # Original validation message if any
    severity: str = "Violation"  # Severity level (Violation, Warning, Info)
    source_constraint_query: Optional[str] = None  # SPARQL query if available

    # Additional context that might be useful for explanation
    context: Dict[str, Union[str, int, float, bool]] = field(default_factory=dict)


@dataclass
class JustificationNode:
    """Node in a justification tree explaining a constraint violation"""

    statement: str  # Human-readable statement
    type: str  # Type of justification node (e.g., "premise", "inference", "conclusion")
    children: List["JustificationNode"] = field(default_factory=list)
    evidence: Optional[str] = None  # Supporting evidence (e.g., SPARQL query, triples)

    def add_child(self, child: "JustificationNode") -> None:
        """Add a child node to this node"""
        self.children.append(child)


@dataclass
class JustificationTree:
    """Tree structure explaining why a constraint was violated"""

    root: JustificationNode
    violation: ConstraintViolation

    def to_dict(self) -> Dict:
        """Convert the tree to a dictionary representation"""

        def node_to_dict(node: JustificationNode) -> Dict:
            return {
                "statement": node.statement,
                "type": node.type,
                "evidence": node.evidence,
                "children": [node_to_dict(child) for child in node.children],
            }

        return {
            "violation": {
                "focus_node": self.violation.focus_node,
                "shape_id": self.violation.shape_id,
                "constraint_id": self.violation.constraint_id,
                "violation_type": self.violation.violation_type.value,
                "property_path": self.violation.property_path,
                "value": self.violation.value,
                "message": self.violation.message,
                "severity": self.violation.severity,
                "context": self.violation.context,
            },
            "justification": node_to_dict(self.root),
        }


@dataclass
class DomainContext:
    """Relevant domain context retrieved for explaining a violation"""

    ontology_fragments: List[str] = field(
        default_factory=list
    )  # Relevant ontology snippets
    shape_documentation: List[str] = field(
        default_factory=list
    )  # Documentation from shapes
    similar_cases: List[Dict] = field(default_factory=list)  # Similar violation cases
    domain_rules: List[str] = field(default_factory=list)  # Domain-specific rules


@dataclass
class ExplanationOutput:
    """Final output containing both formal and natural language explanations"""

    violation: ConstraintViolation
    justification_tree: JustificationTree
    retrieved_context: DomainContext
    natural_language_explanation: str
    correction_suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert the explanation to a dictionary representation"""
        return {
            "violation": {
                "focus_node": self.violation.focus_node,
                "shape_id": self.violation.shape_id,
                "constraint_id": self.violation.constraint_id,
                "violation_type": self.violation.violation_type.value,
                "property_path": self.violation.property_path,
                "value": self.violation.value,
                "message": self.violation.message,
                "severity": self.violation.severity,
            },
            "justification_tree": self.justification_tree.to_dict(),
            "retrieved_context": {
                "ontology_fragments": self.retrieved_context.ontology_fragments,
                "shape_documentation": self.retrieved_context.shape_documentation,
                "similar_cases": self.retrieved_context.similar_cases,
                "domain_rules": self.retrieved_context.domain_rules,
            },
            "natural_language_explanation": self.natural_language_explanation,
            "correction_suggestions": self.correction_suggestions,
        }
