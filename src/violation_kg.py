import rdflib
from rdflib import Namespace, Graph, Literal, URIRef
from rdflib.namespace import RDF
import json  

from xshacl_architecture import ExplanationOutput, JustificationTree, DomainContext
from violation_signature import ViolationSignature

import logging

logger = logging.getLogger("xshacl.violation_kg")

XSH = Namespace("http://xschacl.org/#")

class ViolationKnowledgeGraph:
    def __init__(self,
                 ontology_path: str = "data/xshacl_ontology.ttl",
                 kg_path: str = "data/validation_kg.ttl"):
        self.ontology_path = ontology_path
        self.kg_path = kg_path
        self.store = "BerkeleyDB"   
        self.graph = Graph(store=self.store, identifier="violation_kg")
        self.graph.open(kg_path, create=True)  # Open the store
        self.graph.bind("xshacl", XSH)


        # Load the ontology definitions (TBox)
        self.graph.parse(self.ontology_path, format="turtle")
        
        # If there's existing instance data, load it
        try:
            self.graph.parse(self.kg_path, format="turtle")
        except FileNotFoundError:
            # If there's no existing KG file yet, skip
            pass

    def save_kg(self):
        """Serialize the instance data (not rewriting the ontology)."""
        # If we want to write out only new instance data, we have options:
        # 1. Write out the entire merged graph (ontology + data)
        # 2. Or separate the TBox from the ABox. This can get more complex.
        #
        # For simplicity, let's just write everything for now.
        self.graph.serialize(destination=self.kg_path, format="turtle")

    # ... the rest of your methods ...

    
    def load_kg(self):
        """Load the RDF graph from the TTL file (if it exists)."""
        self.graph = rdflib.Graph()
        self.graph.parse(self.kg_path, format="turtle")
    
    def signature_to_uri(self, sig: ViolationSignature) -> URIRef:
        """
        Create a stable URIRef for a given signature. 
        You can come up with your own hashing or naming scheme.
        """
        # A naive approach is to generate a short hash from the signature fields:
        import hashlib
        
        # Build a canonical string from the essential fields
        sorted_params = sorted(sig.constraint_params.items())
        signature_string = (
            f"{sig.constraint_id}|{sig.property_path}|{sig.violation_type}|{sorted_params}"
        )
        hex_digest = hashlib.md5(signature_string.encode("utf-8")).hexdigest()
        
        # Construct a URI under your xsh: namespace:
        return XSH[f"sig_{hex_digest}"]
    
    def has_violation(self, sig: ViolationSignature) -> bool:
        """
        Check if a node in the KG exists with the same signature fields.
        """
        sig_uri = self.signature_to_uri(sig)
        return (sig_uri, RDF.type, XSH.ViolationSignature) in self.graph
    
    def get_explanation(self, sig: ViolationSignature) -> ExplanationOutput:
        """
        Retrieve the explanation from the KG for a given signature.
        Here we assume the stored info is enough to reconstruct an ExplanationOutput.
        """
        sig_uri = self.signature_to_uri(sig)
        
        # Find the linked Explanation node
        expl_uri = self.graph.value(subject=sig_uri, predicate=XSH.hasExplanation)
        if expl_uri is None:
            raise ValueError("No explanation found for signature in KG.")
        
        if (expl_uri, None, None) in self.graph:
            # Retrieve data from KG
            violation = str(self.graph.value(expl_uri, XSH.violation))
            explanation = str(self.graph.value(expl_uri, XSH.explanation))
            correction_suggestions = [
                str(o) for o in self.graph.objects(expl_uri, XSH.correctionSuggestion)
            ]
            justification_tree_json = str(self.graph.value(expl_uri, XSH.justificationTree))
            context_json = str(self.graph.value(expl_uri, XSH.context))

            justification_tree = JustificationTree(**json.loads(justification_tree_json))
            retrieved_context = DomainContext(**json.loads(context_json))

            return ExplanationOutput(violation, justification_tree, retrieved_context, explanation,
                                     correction_suggestions)
        return None
    
    def add_violation(self, sig: ViolationSignature, explanation: ExplanationOutput):
        """
        Add a new violation signature and explanation to the KG.
        No-op if it already exists.
        """
        # If we already have it, do nothing nor update the explanation
        if self.has_violation(sig):
            return
        
        sig_uri = self.signature_to_uri(sig)
        self.graph.add((sig_uri, RDF.type, XSH.ViolationSignature))
        
        violation = explanation.violation
        violation_uri = XSH[f"violation_{hash(str(violation))}"]  # Unique URI

        self.graph.add((violation_uri, RDF.type, XSH.Violation))
        self.graph.add((violation_uri, XSH.focusNode, Literal(violation.focus_node)))
        self.graph.add((violation_uri, XSH.shapeId, Literal(violation.shape_id)))
        self.graph.add((violation_uri, XSH.constraintId, Literal(violation.constraint_id)))
        self.graph.add(
            (violation_uri, XSH.violationType, Literal(violation.violation_type.value))
        )
        if violation.property_path:
            self.graph.add((violation_uri, XSH.propertyPath, Literal(violation.property_path)))
        if violation.value:
            self.graph.add((violation_uri, XSH.value, Literal(violation.value)))
        if violation.message:
            self.graph.add((violation_uri, XSH.message, Literal(violation.message)))
        self.graph.add(
            (violation_uri, XSH.explanation, Literal(explanation.natural_language_explanation))
        )
        for suggestion in explanation.correction_suggestions:
            self.graph.add((violation_uri, XSH.correctionSuggestion, Literal(suggestion)))
        self.graph.add(
            (
                violation_uri,
                XSH.justificationTree,
                Literal(json.dumps(explanation.justification_tree.to_dict())),
            )
        )
        self.graph.add(
            (violation_uri, XSH.context, Literal(json.dumps(explanation.retrieved_context.__dict__)))
        )

    
    def clear(self):
        """Clear the in-memory graph."""
        self.graph = rdflib.Graph()
        self.save_kg()
    
    def size(self) -> int:
        """Return the number of triples in the graph."""
        return len(self.graph)
    
    def close(self):
        """Closes the underlying store."""
        self.graph.close()
