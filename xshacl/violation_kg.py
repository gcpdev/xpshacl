from typing import Dict, Set
from dataclasses import dataclass, field
from xshacl_architecture import ExplanationOutput, ConstraintViolation, ViolationSignature

import logging

logger = logging.getLogger("xshacl.violation_kg")


class ViolationKnowledgeGraph:
    """
    Knowledge Graph for storing and retrieving ConstraintViolation explanations,
    optimized for handling semantically equivalent violations.
    """

    def __init__(self):
        self._violation_explanations: Dict[ViolationSignature, ExplanationOutput] = {}
        self._violation_signatures: Set[ViolationSignature] = (
            set()
        )  # Keep track of signatures for faster lookup

    def add_violation(
        self, violation_signature: ViolationSignature, explanation: ExplanationOutput
    ):
        """Adds a new violation and its explanation to the KG."""
        if not isinstance(violation_signature, ViolationSignature):
            raise TypeError(
                "violation_signature must be an instance of ViolationSignature"
            )
        if not isinstance(explanation, ExplanationOutput):
            raise TypeError("explanation must be an instance of ExplanationOutput")

        if violation_signature not in self._violation_signatures:
            self._violation_explanations[violation_signature] = explanation
            self._violation_signatures.add(violation_signature)
            logger.debug(f"Violation with signature {violation_signature} added to KG.")
        else:
            logger.warning(
                f"Attempted to add duplicate violation signature: {violation_signature}. Ignoring."
            )

    def has_violation(self, violation_signature: ViolationSignature) -> bool:
        """Checks if a violation with the given signature already exists in the KG."""
        return violation_signature in self._violation_signatures

    def get_explanation(
        self, violation_signature: ViolationSignature
    ) -> ExplanationOutput:
        """Retrieves the explanation for a given violation signature."""
        if not self.has_violation(violation_signature):
            raise ValueError(
                f"Violation with signature {violation_signature} not found in KG."
            )
        return self._violation_explanations[violation_signature]

    def size(self) -> int:
        """Returns the number of violations stored in the KG."""
        return len(self._violation_signatures)

    def clear(self):
        """Clears all violations from the KG."""
        self._violation_explanations.clear()
        self._violation_signatures.clear()
        logger.info("ViolationKG cleared.")
