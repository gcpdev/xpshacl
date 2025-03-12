import argparse
import json
import logging
from rdflib import Graph

from extended_shacl_validator import ExtendedShaclValidator
from justification_tree_builder import JustificationTreeBuilder
from context_retriever import ContextRetriever
from explanation_generator import ExplanationGenerator, LocalExplanationGenerator
from xshacl_architecture import ExplanationOutput
from violation_kg import ViolationKnowledgeGraph
from violation_signature_factory import create_violation_signature

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("xshacl")

def main():
    parser = argparse.ArgumentParser(description="xSHACL: Explainable SHACL Validation")
    parser.add_argument("--data", required=True, help="Path to the RDF data file")
    parser.add_argument("--shapes", required=True, help="Path to the SHACL shapes file")
    parser.add_argument("--local", action="store_true", help="Use local LLM (Ollama)")
    parser.add_argument(
        "--model", default="gpt2", help="Hugging Face model name (if not using --local)"
    )
    parser.add_argument(
        "--inference",
        default="none",
        help="Inference option for SHACL validation (none, rdfs, owlrl, etc.)",
    )

    args = parser.parse_args()

    # Load data and shapes graphs
    try:
        data_graph = Graph().parse(args.data, format="ttl")
        shapes_graph = Graph().parse(args.shapes, format="ttl")
    except Exception as e:
        logger.error(f"Error loading RDF graphs: {e}")
        return

    # Initialize components
    validator = ExtendedShaclValidator(shapes_graph, args.inference)
    justification_builder = JustificationTreeBuilder(data_graph, shapes_graph)
    context_retriever = ContextRetriever(data_graph, shapes_graph)
    violation_kg = ViolationKnowledgeGraph()

    if args.local:
        explanation_generator = LocalExplanationGenerator()
    else:
        explanation_generator = ExplanationGenerator(args.model)

    # Validate and explain
    is_valid, validation_graph, violations = validator.validate(data_graph)

    if not violations:
        logger.info("Validation successful. No violations found.")
        return

    explanations = []
    for violation in violations:
        # 1. Build the justification tree
        jt = justification_builder.build_justification_tree(violation)
        # 2. Retrieve any domain context
        context = context_retriever.retrieve_context(violation)
        # 3. Generate signature
        signature = create_violation_signature(violation)
        
        # 4. Check the KG cache
        if violation_kg.has_violation(signature):
            explanation = violation_kg.get_explanation(signature)
        else:
            explanation = explanation_generator.generate_explanation(
                violation, jt, context
            )
            # Store new explanation in KG
            violation_kg.add_violation(signature, explanation)
        
        explanations.append(explanation)

    # Output explanations
    for explanation in explanations:
        print(json.dumps(explanation.to_dict(), indent=2))


if __name__ == "__main__":
    main()
