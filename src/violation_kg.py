from typing import Dict, Set
from dataclasses import dataclass, field
from xshacl_architecture import ExplanationOutput, ConstraintViolation

import logging, os

logger = logging.getLogger("xshacl.violation_kg")


# violation_kg.py
import rdflib
from rdflib import Namespace, Graph, Literal, URIRef
from rdflib.namespace import RDF, RDFS
import json  # if you store constraint_params as JSON
from typing import Optional

from xshacl_architecture import ExplanationOutput
from violation_signature import ViolationSignature

XSH = Namespace("http://xschacl.org/#")

class ViolationKnowledgeGraph:
    def __init__(self,
                 ontology_path: str = "data/xshacl_ontology.ttl",
                 kg_path: str = "data/validation_kg.ttl"):
        self.ontology_path = ontology_path
        self.kg_path = kg_path
        self.graph = rdflib.Graph()

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
        
        # Get any fields you stored, e.g. naturalLanguageText, correctionSuggestions, etc.
        nlt = self.graph.value(subject=expl_uri, predicate=XSH.naturalLanguageText)
        cs = self.graph.value(subject=expl_uri, predicate=XSH.correctionSuggestions)
        
        # You can store more fields (formal details, etc.) as needed
        # Return an ExplanationOutput object
        return ExplanationOutput(
            natural_language_explanation=str(nlt),
            correction_suggestions=[str(cs)] if cs else []
        )
    
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
        
        # Set data properties
        self.graph.add((sig_uri, XSH.constraintComponent, Literal(sig.constraint_id)))
        
        if sig.property_path:
            self.graph.add((sig_uri, XSH.propertyPath, Literal(sig.property_path)))
        
        if sig.violation_type:
            self.graph.add((sig_uri, XSH.violationType, Literal(sig.violation_type)))
        
        if sig.constraint_params:
            # For simplicity, store them as a JSON string
            json_params = json.dumps(sig.constraint_params, sort_keys=True)
            self.graph.add((sig_uri, XSH.constraintParams, Literal(json_params)))
        
        # Create explanation node
        expl_uri = URIRef(str(sig_uri) + "_explanation")
        self.graph.add((expl_uri, RDF.type, XSH.Explanation))
        self.graph.add((
            sig_uri,
            XSH.hasExplanation,
            expl_uri
        ))
        
        # Store natural language text
        if explanation.natural_language_explanation:
            self.graph.add((
                expl_uri,
                XSH.naturalLanguageText,
                Literal(explanation.natural_language_explanation)
            ))
        
        # Store multiple correction suggestions as a single text
        if explanation.correction_suggestions:
            joined_suggestions = "\n".join(explanation.correction_suggestions)
            self.graph.add((
                expl_uri,
                XSH.correctionSuggestions,
                Literal(joined_suggestions)
            ))
        
        self.save_kg()
    
    def clear(self):
        """Clear the in-memory graph."""
        self.graph = rdflib.Graph()
        self.save_kg()
    
    def size(self) -> int:
        """Return the number of triples in the graph."""
        return len(self.graph)
