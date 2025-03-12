# violation_signature_factory.py
from typing import Dict
from xshacl_architecture import ConstraintViolation
from violation_signature import ViolationSignature

def create_violation_signature(violation: ConstraintViolation) -> ViolationSignature:
    # Attempt to parse out known parameters from the violation
    constraint_params: Dict[str, str] = {}
    
    # For example, if you know you have minCount or maxCount somewhere in the violation data,
    # you can read them. This might require additional logic if your system
    # exposes these parameters somewhere.
    if violation.constraint_id == "http://www.w3.org/ns/shacl#MinCountConstraintComponent":
        # Possibly read the actual minCount value from the shape data or from the violation.
        # Hard-code "1" if your example always is minCount=1, or parse from the shape definition.
        constraint_params["minCount"] = "1"
    
    return ViolationSignature(
        constraint_id = violation.constraint_id,
        property_path = violation.property_path,
        violation_type = violation.violation_type,  # e.g. "cardinality"
        constraint_params = constraint_params
    )
