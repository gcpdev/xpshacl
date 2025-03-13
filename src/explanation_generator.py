import os
import json
import logging
from typing import List
import ollama
import openai
from dotenv import load_dotenv

from rdflib import Graph

from xshacl_architecture import (
    ConstraintViolation,
    JustificationTree,
    DomainContext,
    ExplanationOutput,
    ViolationType,
)
from context_retriever import ContextRetriever
from extended_shacl_validator import ExtendedShaclValidator
from justification_tree_builder import JustificationTreeBuilder

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("xshacl")

# --- LLM Integration for Natural Language Generation ---

explanations_prompt = """INSTRUCTIONS:
        Return only a human-readable explanation, and nothing else.
        Do not use the values of the violation in your explanation, only the type of violation - make the description generic but understandable by the user.
        E.g.: Do say 'it was provided a negative value which does not comply with the restriction for the property X', instead of 'the value -5 does not comply with the minInclusive restriction of X'.
        Provide the justification only, no context, no small introductory phrasing.
        Be short and straight to the point, but do include all relevant information to the user.
        """

suggestions_prompt = """INSTRUCTIONS:
        Suggest possible corrections. 
        Do not use the values of the violation in your suggestions, only the type of violation - make the description generic but understandable by the user.
        E.g.: Do say 'change the negative value to a positive one of the property X or change your SHACL rule to allow positive values',
         instead of 'change the value -5 to 0 or more to comply with the minInclusive restriction of X'.
        Be short and straight to the point, and do include suggestions to fix only what was reported as violation."
        """


class ExplanationGenerator:
    """Generates natural language explanations using an LLM"""

    def __init__(self, model_name: str = "gpt-4o-mini-2024-07-18"):
        self.model_name = model_name
        if "gpt" in model_name:
            openai.api_key = os.getenv("OPENAI_API_KEY")
            openai.base_url = "https://api.openai.com/v1/"
            if not openai.api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set.")
        elif "gemini" in model_name:
            openai.api_key = os.getenv("GEMINI_API_KEY")
            openai.base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
            if not openai.api_key:
                raise ValueError("GEMINI_API_KEY environment variable not set.")
        elif "claude" in model_name:
            openai.api_key = os.getenv("ANTHROPIC_API_KEY")
            openai.base_url = "https://api.anthropic.com/v1/"
            if not openai.api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable not set.")

    def _generate_explanation_text(
        self,
        violation: ConstraintViolation,
        justification_tree: JustificationTree,
        context: DomainContext,
    ) -> str:
        """
        Internal helper that calls the OpenAI Chat Completion and returns a raw string.
        """
        prompt = f"Explain the following SHACL violation: {violation.message or 'Unknown violation'}. "
        prompt += f"Justification: {json.dumps(justification_tree.to_dict(), indent=2, default=str)}. "
        prompt += (
            f"Relevant context: {json.dumps(context.__dict__, indent=2, default=str)}. "
        )
        prompt += explanations_prompt

        try:
            response = openai.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return f"Error generating explanation: {e}"

    def _generate_correction_suggestions_text(
        self, violation: ConstraintViolation, context: DomainContext
    ) -> List[str]:
        """
        Internal helper that calls the OpenAI Chat Completion for suggestions
        and returns a list of strings.
        """
        prompt = f"Given the following SHACL violation: {violation.message or 'Unknown violation'}. "
        prompt += f"Relevant context: {json.dumps(context.__dict__, indent=2)}. "
        prompt += suggestions_prompt

        try:
            response = openai.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
            )
            return [response.choices[0].message.content.strip()]
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            return [f"Error generating correction suggestions: {e}"]

    def generate_explanation_output(
        self,
        violation: ConstraintViolation,
        justification_tree: JustificationTree,
        context: DomainContext,
    ) -> ExplanationOutput:
        """
        Public method that returns an ExplanationOutput object,
        packaging the text from the LLM into the correct fields.
        """
        explanation_text = self._generate_explanation_text(
            violation, justification_tree, context
        )
        suggestions = self._generate_correction_suggestions_text(violation, context)

        return ExplanationOutput(
            violation=violation,
            justification_tree=justification_tree,
            retrieved_context=context,
            natural_language_explanation=explanation_text,
            correction_suggestions=suggestions,
        )


class ExplainableShaclSystem:
    """Combines all components to provide explainable SHACL validation"""

    def __init__(
        self,
        data_graph: Graph,
        shapes_graph: Graph,
        inference: str = "none",
        model: str = "gpt-4o-mini-2024-07-18",
    ):
        self.validator = ExtendedShaclValidator(shapes_graph, inference)
        self.justification_builder = JustificationTreeBuilder(data_graph, shapes_graph)
        self.context_retriever = ContextRetriever(data_graph, shapes_graph)
        self.explanation_generator = ExplanationGenerator(model_name=model)

    def explain_validation(self, data_graph: Graph) -> List[ExplanationOutput]:
        """Validates a data graph and generates explanations for violations"""
        is_valid, validation_graph, violations = self.validator.validate(data_graph)
        explanations = []

        for violation in violations:
            justification_tree = self.justification_builder.build_tree(violation)
            retrieved_context = self.context_retriever.retrieve_context(violation)
            natural_language_explanation = (
                self.explanation_generator._generate_explanation_text(
                    violation, justification_tree, retrieved_context
                )
            )
            correction_suggestions = (
                self.explanation_generator._generate_correction_suggestions_text(
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

    def generate_explanation_output(
        self,
        violation: ConstraintViolation,
        justification_tree: JustificationTree,
        context: DomainContext,
    ) -> str:
        """Generates a natural language explanation for a violation using Ollama"""

        prompt = f"Explain the following SHACL violation: {violation.message or 'Unknown violation'}. "
        prompt += f"Justification: {json.dumps(justification_tree.to_dict(), indent=2, default=str)}. "
        prompt += (
            f"Relevant context: {json.dumps(context.__dict__, indent=2, default=str)}. "
        )
        prompt += explanations_prompt

        response = ollama.chat(
            model=self.model_name, messages=[{"role": "user", "content": prompt}]
        )
        if self.model_name == "gemma:2b":
            if "".join(response["message"]["content"].split("\n")[1:]) != "":
                return "".join(response["message"]["content"].split("\n")[1:])
        return response["message"]["content"]

    def generate_correction_suggestions(
        self, violation: ConstraintViolation, context: DomainContext
    ) -> List[str]:
        """Generates correction suggestions for a violation using Ollama"""
        prompt = f"Given the following SHACL violation: {violation.message or 'Unknown violation'}. "
        prompt += (
            f"Relevant context: {json.dumps(context.__dict__, indent=2, default=str)}. "
        )
        prompt += suggestions_prompt

        response = ollama.chat(
            model=self.model_name, messages=[{"role": "user", "content": prompt}]
        )
        return [response["message"]["content"]]
