import os
import json
import logging
from typing import Dict, List, Optional, Set, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import ollama

# Import necessary libraries
from rdflib import Graph, URIRef, Literal, BNode, Namespace
from rdflib.namespace import RDF, RDFS, SH, XSD
from pyshacl import validate
import re
from transformers import pipeline

# Import your existing components
from xshacl_architecture import (
    ConstraintViolation,
    JustificationTree,
    DomainContext,
    ExplanationOutput,
)
from context_retriever import ContextRetriever
from extended_shacl_validator import ExtendedShaclValidator
from justification_tree_builder import JustificationTreeBuilder

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("xshacl")

# --- LLM Integration for Natural Language Generation ---


class ExplanationGenerator:
    """Generates natural language explanations using an LLM"""

    def __init__(self, model_name: str = "qwq"):  # or "t5-small"
        self.generator = pipeline("text-generation", model=model_name)

    def generate_explanation(
        self,
        violation: ConstraintViolation,
        justification_tree: JustificationTree,
        context: DomainContext,
    ) -> str:
        """Generates a natural language explanation for a violation"""

        prompt = f"Explain the following SHACL violation: {violation.message or 'Unknown violation'}. "
        prompt += (
            f"Justification: {json.dumps(justification_tree.to_dict(), indent=2)}. "
        )
        prompt += f"Relevant context: {json.dumps(context.__dict__, indent=2)}. "
        prompt += "Generate a human-readable explanation."

        generated_text = self.generator(prompt, max_length=250, num_return_sequences=1)[
            0
        ]["generated_text"]
        return generated_text

    def generate_correction_suggestions(
        self, violation: ConstraintViolation, context: DomainContext
    ) -> List[str]:
        """Generates correction suggestions for a violation"""
        prompt = f"Given the following SHACL violation: {violation.message or 'Unknown violation'}. "
        prompt += f"Relevant context: {json.dumps(context.__dict__, indent=2)}. "
        prompt += "Suggest possible corrections."

        generated_text = self.generator(prompt, max_length=150, num_return_sequences=1)[
            0
        ]["generated_text"]
        return [generated_text]


class ExplainableShaclSystem:
    """Combines all components to provide explainable SHACL validation"""

    def __init__(self, data_graph: Graph, shapes_graph: Graph, inference: str = "none"):
        self.validator = ExtendedShaclValidator(shapes_graph, inference)
        self.justification_builder = JustificationTreeBuilder(data_graph, shapes_graph)
        self.context_retriever = ContextRetriever(data_graph, shapes_graph)
        self.explanation_generator = ExplanationGenerator()

    def explain_validation(self, data_graph: Graph) -> List[ExplanationOutput]:
        """Validates a data graph and generates explanations for violations"""
        is_valid, validation_graph, violations = self.validator.validate(data_graph)
        explanations = []

        for violation in violations:
            justification_tree = self.justification_builder.build_tree(violation)
            retrieved_context = self.context_retriever.retrieve_context(violation)
            natural_language_explanation = (
                self.explanation_generator.generate_explanation(
                    violation, justification_tree, retrieved_context
                )
            )
            correction_suggestions = (
                self.explanation_generator.generate_correction_suggestions(
                    violation, retrieved_context
                )
            )

            explanation_output = ExplanationOutput(
                violation=violation,
                justification_tree=justification_tree,
                retrieved_context=retrieved_context,
                natural_language_explanation=natural_language_explanation,
                correction_suggestions=correction_suggestions,
            )
            explanations.append(explanation_output)

        return explanations


class LocalExplanationGenerator:
    """Generates natural language explanations using Ollama"""

    def __init__(self, model_name: str = "gemma:2b"):
        self.model_name = model_name

    def generate_explanation(
        self,
        violation: ConstraintViolation,
        justification_tree: JustificationTree,
        context: DomainContext,
    ) -> str:
        """Generates a natural language explanation for a violation using Ollama"""

        prompt = f"Explain the following SHACL violation: {violation.message or 'Unknown violation'}. "
        prompt += (
            f"Justification: {json.dumps(justification_tree.to_dict(), indent=2)}. "
        )
        prompt += f"Relevant context: {json.dumps(context.__dict__, indent=2)}. "
        prompt += """INSTRUCTIONS:
        Return only a human-readable explanation, and nothing else. Provide the justification only, no context, no small introductory phrasing.
        Be short and straight to the point, but do include all relevant information to the user.
        """

        response = ollama.chat(
            model=self.model_name, messages=[{"role": "user", "content": prompt}]
        )
        if self.model_name == "gemma:2b":
            if ''.join(response["message"]["content"].split("\n")[1:]) != '':
                return ''.join(response["message"]["content"].split("\n")[1:])
        return response["message"]["content"]

    def generate_correction_suggestions(
        self, violation: ConstraintViolation, context: DomainContext
    ) -> List[str]:
        """Generates correction suggestions for a violation using Ollama"""
        prompt = f"Given the following SHACL violation: {violation.message or 'Unknown violation'}. "
        prompt += f"Relevant context: {json.dumps(context.__dict__, indent=2)}. "
        prompt += "Suggest possible corrections. Be short and straight to the point, and do include suggestions to fix only what was reported as violation."

        response = ollama.chat(
            model=self.model_name, messages=[{"role": "user", "content": prompt}]
        )
        return [response["message"]["content"]]


# --- Example Usage ---

if __name__ == "__main__":
    # Load your data and shapes graphs
    data_graph = Graph().parse(
        "example_data.ttl", format="ttl"
    )  # Replace with your data file
    shapes_graph = Graph().parse(
        "example_shapes.ttl", format="ttl"
    )  # Replace with your shapes file

    system = ExplainableShaclSystem(data_graph, shapes_graph)
    explanations = system.explain_validation(data_graph)

    for explanation in explanations:
        print(json.dumps(explanation.to_dict(), indent=2))
