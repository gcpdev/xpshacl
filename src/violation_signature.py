from dataclasses import dataclass, field
from typing import Optional, Dict


@dataclass(frozen=True)
class ViolationSignature:
    """
    A unique signature that identifies the *type* of a SHACL violation
    independently of the specific focus node or shape ID.
    """

    constraint_id: str
    property_path: Optional[str]
    violation_type: Optional[str] = None
    constraint_params: Dict[str, str] = field(default_factory=dict)

    def __hash__(self):
        sorted_params = tuple(sorted(self.constraint_params.items()))
        return hash(
            (self.constraint_id, self.property_path, self.violation_type, sorted_params)
        )

    def __eq__(self, other):
        if not isinstance(other, ViolationSignature):
            return False
        return (
            self.constraint_id == other.constraint_id
            and self.property_path == other.property_path
            and self.violation_type == other.violation_type
            and dict(self.constraint_params) == dict(other.constraint_params)
        )
