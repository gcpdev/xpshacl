from dataclasses import dataclass, field
from typing import Optional, Dict

@dataclass(frozen=True)
class ViolationSignature:
    """
    A unique signature that identifies the *type* of a SHACL violation
    independently of the specific focus node or shape ID.
    """
    constraint_id: str  # e.g. "http://www.w3.org/ns/shacl#MinCountConstraintComponent"
    property_path: Optional[str]  # e.g. "http://example.org/hasName"
    violation_type: Optional[str] = None  # e.g. "cardinality"
    constraint_params: Dict[str, str] = field(default_factory=dict)
    
    # If needed, you can define a __hash__ and __eq__ explicitly, or rely
    # on dataclasses’ (frozen=True) auto-implementations.
    # For example, to handle dictionary ordering in constraint_params,
    # you might want to provide a canonical representation:
    #
    # def __hash__(self):
    #     sorted_params = tuple(sorted(self.constraint_params.items()))
    #     return hash((self.constraint_id, self.property_path, self.violation_type, sorted_params))

    # def __eq__(self, other):
    #     if not isinstance(other, ViolationSignature):
    #         return False
    #     return (
    #         self.constraint_id == other.constraint_id and
    #         self.property_path == other.property_path and
    #         self.violation_type == other.violation_type and
    #         dict(self.constraint_params) == dict(other.constraint_params)
    #     )
