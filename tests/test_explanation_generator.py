import sys, os, unittest, json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from unittest.mock import patch
from rdflib import Graph, URIRef, Literal, Namespace
from xpshacl_architecture import (
    ConstraintViolation,
    JustificationTree,
    JustificationNode,
    DomainContext,
    ViolationType,
)
from explanation_generator import (
    ExplanationGenerator,
    explanations_prompt,
)  # Corrected import, only need one

# Define default language used in tests for clarity
DEFAULT_TEST_LANGUAGE = "en"


class TestExplanationGenerator(unittest.TestCase):
    def setUp(self):
        # Make sure OPENAI_API_KEY is set for initialization, even if mocked later
        # You might need to set a dummy value if it's not present during test runs
        os.environ["OPENAI_API_KEY"] = "test_key"
        self.explanation_generator = ExplanationGenerator(model_name="test_model")

    @patch("explanation_generator.openai.chat.completions.create")
    def test_generate_explanation_text_success(self, mock_create):
        # Mock the OpenAI API response
        mock_create.return_value.choices = [
            type(
                "obj",
                (object,),
                {"message": type("obj", (object,), {"content": " Test explanation "})},
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
            violation_type=ViolationType.OTHER,
        )
        justification_tree = JustificationTree(
            JustificationNode("test", "test"), violation
        )
        context = DomainContext()
        # Add some graph data to ensure json.dumps default=str handles them if needed
        context.data_graph = Graph()
        context.shapes_graph = Graph()
        context.focus_node_context = {}
        context.property_shape_context = {}

        # Call the method (uses default language 'en')
        explanation = self.explanation_generator._generate_explanation_text(
            violation, justification_tree, context
        )

        # Assert that the method returns the expected value (stripped)
        self.assertEqual(explanation, "Test explanation")

        # Assert that the OpenAI API was called with the correct parameters
        expected_prompt = (
            f"Explain the following SHACL violation in {DEFAULT_TEST_LANGUAGE} (ISO 639-1 code): Test violation message. "
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
            violation_type=ViolationType.OTHER,
        )
        justification_tree = JustificationTree(
            JustificationNode("test", "test"), violation
        )
        context = DomainContext()
        # Minimal context for this test
        context.data_graph = Graph()
        context.shapes_graph = Graph()

        # Call the method (uses default language 'en')
        explanation = self.explanation_generator._generate_explanation_text(
            violation, justification_tree, context
        )

        # Assert that the method returns the expected value
        self.assertEqual(explanation, "Test explanation")

        # Assert that the OpenAI API was called with the correct parameters
        expected_prompt = (
            f"Explain the following SHACL violation in {DEFAULT_TEST_LANGUAGE} (ISO 639-1 code): Unknown violation. "
            f"Justification: {json.dumps(justification_tree.to_dict(), indent=2, default=str)}. "
            f"Relevant context: {json.dumps(context.__dict__, indent=2, default=str)}. "
        )
        expected_prompt += explanations_prompt

        mock_create.assert_called_once_with(
            model="test_model", messages=[{"role": "user", "content": expected_prompt}]
        )

    @patch("explanation_generator.openai.chat.completions.create")
    def test_generate_explanation_text_api_error(self, mock_create):
        # Mock the OpenAI API to raise an Exception (as caught in the method)
        api_error_message = "API Error"
        mock_create.side_effect = Exception(api_error_message)

        # Create dummy objects for the method parameters
        violation = ConstraintViolation(
            focus_node=URIRef("http://example.org/node"),
            value=Literal("test value"),
            constraint_id=URIRef("http://example.org/constraint"),
            shape_id=URIRef("http://example.org/shape"),
            severity="violation",
            message="Test violation message",
            violation_type=ViolationType.OTHER,
        )
        justification_tree = JustificationTree(
            JustificationNode("test", "test"), violation
        )
        context = DomainContext()
        context.data_graph = Graph()
        context.shapes_graph = Graph()

        # Call the method (uses default language 'en')
        explanation = self.explanation_generator._generate_explanation_text(
            violation, justification_tree, context
        )

        # Assert that the method returns the expected error message
        expected_error_message = f"Error generating explanation in {DEFAULT_TEST_LANGUAGE}: {api_error_message}"
        self.assertEqual(explanation, expected_error_message)


if __name__ == "__main__":
    unittest.main()
