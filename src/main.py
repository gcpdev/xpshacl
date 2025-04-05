import argparse, json, time, logging
from rdflib import Graph

from extended_shacl_validator import ExtendedShaclValidator
from justification_tree_builder import JustificationTreeBuilder
from context_retriever import ContextRetriever
from explanation_generator import ExplanationGenerator, LocalExplanationGenerator
from xpshacl_architecture import ExplanationOutput
from violation_kg import ViolationKnowledgeGraph
from violation_signature_factory import create_violation_signature

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("xpshacl")

def main():
    start_time = time.time()  # Record the start time

    parser = argparse.ArgumentParser(description="xpSHACL: Explainable SHACL Validation")
    parser.add_argument("--data", required=True, help="Path to the RDF data file")
    parser.add_argument("--shapes", required=True, help="Path to the SHACL shapes file")
    parser.add_argument("--local", action="store_true", help="Use local LLM (Ollama)")
    parser.add_argument(
        "--model", default="gpt-4o-mini-2024-07-18", help="Provider's API model name (if not using --local)"
    )
    parser.add_argument(
        "--inference",
        default="none",
        help="Inference option for SHACL validation (none, rdfs, owlrl, etc.)",
    )
    parser.add_argument(
        "--language",
        default="en",
        help="Language code (ISO-639-1) or comma-separated list of language codes for explanations (default: en)",
    )

    args = parser.parse_args()

    languages = [lang.strip() for lang in args.language.lower().split(',')]

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

        # 4. Check the KG cache for each requested language
        language_explanations = {}
        for lang in languages:
            cached_explanation = violation_kg.get_explanation(signature, lang)
            if cached_explanation:
                language_explanations[lang] = cached_explanation

        # 5. Generate missing explanations using the LLM
        languages_to_generate = [lang for lang in languages if lang not in language_explanations]
        if languages_to_generate:
            llm_output = explanation_generator.generate_explanation_output(
                violation, jt, context, languages_to_generate
            )
            # Store the generated explanations in the KG
            for lang, (nlt, cs) in llm_output.items():
                explanation = ExplanationOutput(
                    natural_language_explanation=nlt,
                    correction_suggestions=cs,
                    violation=violation,
                    justification_tree=jt,
                    retrieved_context=context,
                    provided_by_model=explanation_generator.model_name if not args.local else "local",
                )
                violation_kg.add_violation(signature, explanation, lang)
                language_explanations[lang] = explanation

        # Combine explanations for all requested languages
        combined_explanation = {lang: language_explanations.get(lang).to_dict() for lang in languages}
        explanations.append(combined_explanation)

    # Output explanations
    print(json.dumps(explanations, indent=2, default=str))

    end_time = time.time()  # Record the end time
    elapsed_time = end_time - start_time  # Calculate the elapsed time

    logger.info(f"Total execution time: {elapsed_time:.4f} seconds")  # Log the elapsed time
    print(f"Total execution time: {elapsed_time:.4f} seconds")  # Print the elapsed time


if __name__ == "__main__":
    main()