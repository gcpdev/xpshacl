# violation_signature_factory.py
from typing import Dict
from xpshacl_architecture import ConstraintViolation
from violation_signature import ViolationSignature


def create_violation_signature(violation: ConstraintViolation) -> ViolationSignature:
    # Attempt to parse out known parameters from the violation
    constraint_params: Dict[str, str] = {}

    return ViolationSignature(
        constraint_id=violation.constraint_id,
        property_path=violation.property_path,
        violation_type=violation.violation_type,
        constraint_params=constraint_params,
    )
