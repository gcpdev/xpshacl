import sys, os, unittest, json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from unittest.mock import patch
from rdflib import Graph, URIRef, Literal, Namespace
from xshacl_architecture import (
    ConstraintViolation,
    JustificationTree,
    JustificationNode,
    DomainContext,
)
from explanation_generator import ExplanationGenerator
from explanation_generator import explanations_prompt
from explanation_generator import explanations_prompt


class TestExplanationGenerator(unittest.TestCase):
    def setUp(self):
        self.explanation_generator = ExplanationGenerator(model_name="test_model")

    @patch("explanation_generator.openai.chat.completions.create")
    def test_generate_explanation_text_success(self, mock_create):
        # Mock the OpenAI API response
        mock_create.return_value.choices = [
            type(
                "obj",
                (object,),
                {"message": type("obj", (object,), {"content": "Test explanation"})},
            )()
        ]

        # Create dummy objects for the method parameters
        violation = ConstraintViolation(
            focus_node=URIRef("http://example.org/node"),
            value=Literal("test value"),
            constraint_id=URIRef("http://example.org/constraint"),
            shape_id=URIRef("http://example.org/shape"),
            severity="violation",
            message="Test violation message",
            violation_type="test",
        )
        justification_tree = JustificationTree(
            JustificationNode("test", "test"), violation
        )
        context = DomainContext()
        context.data_graph = Graph()
        context.shapes_graph = Graph()
        context.focus_node_context = {}
        context.property_shape_context = {}

        # Call the method
        explanation = self.explanation_generator._generate_explanation_text(
            violation, justification_tree, context
        )

        # Assert that the method returns the expected value
        self.assertEqual(explanation, "Test explanation")

        # Assert that the OpenAI API was called with the correct parameters
        expected_prompt = (
            f"Explain the following SHACL violation: Test violation message. "
            f"Justification: {json.dumps(justification_tree.to_dict(), indent=2, default=str)}. "
            f"Relevant context: {json.dumps(context.__dict__, indent=2, default=str)}. "
        )
        expected_prompt += explanations_prompt

        mock_create.assert_called_once_with(
            model="test_model", messages=[{"role": "user", "content": expected_prompt}]
        )

    @patch("explanation_generator.openai.chat.completions.create")
    def test_generate_explanation_text_no_message(self, mock_create):
        # Mock the OpenAI API response
        mock_create.return_value.choices = [
            type(
                "obj",
                (object,),
                {"message": type("obj", (object,), {"content": "Test explanation"})},
            )()
        ]

        # Create dummy objects for the method parameters
        violation = ConstraintViolation(
            focus_node=URIRef("http://example.org/node"),
            value=Literal("test value"),
            constraint_id=URIRef("http://example.org/constraint"),
            shape_id=URIRef("http://example.org/shape"),
            severity="violation",
            message=None,
            violation_type="test",
        )
        justification_tree = JustificationTree(
            JustificationNode("test", "test"), violation
        )
        context = DomainContext()

        # Call the method
        explanation = self.explanation_generator._generate_explanation_text(
            violation, justification_tree, context
        )

        # Assert that the method returns the expected value
        self.assertEqual(explanation, "Test explanation")

        # Assert that the OpenAI API was called with the correct parameters
        expected_prompt = (
            f"Explain the following SHACL violation: Unknown violation. "
            f"Justification: {json.dumps(justification_tree.to_dict(), indent=2, default=str)}. "
            f"Relevant context: {json.dumps(context.__dict__, indent=2, default=str)}. "
        )
        expected_prompt += explanations_prompt

        mock_create.assert_called_once_with(
            model="test_model", messages=[{"role": "user", "content": expected_prompt}]
        )

    @patch("explanation_generator.openai.chat.completions.create")
    def test_generate_explanation_text_api_error(self, mock_create):
        # Mock the OpenAI API to raise an APIError
        mock_create.side_effect = Exception("API Error")

        # Create dummy objects for the method parameters
        violation = ConstraintViolation(
            focus_node=URIRef("http://example.org/node"),
            value=Literal("test value"),
            constraint_id=URIRef("http://example.org/constraint"),
            shape_id=URIRef("http://example.org/shape"),
            severity="violation",
            message="Test violation message",
            violation_type="test",
        )
        justification_tree = JustificationTree(
            JustificationNode("test", "test"), violation
        )
        context = DomainContext()

        # Call the method
        explanation = self.explanation_generator._generate_explanation_text(
            violation, justification_tree, context
        )

        # Assert that the method returns the expected error message
        self.assertEqual(explanation, "Error generating explanation: API Error")
