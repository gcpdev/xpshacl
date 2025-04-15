import argparse, json, time, logging, sys
from rdflib import Graph

from extended_shacl_validator import ExtendedShaclValidator
from justification_tree_builder import JustificationTreeBuilder
from context_retriever import ContextRetriever
from explanation_generator import ExplanationGenerator, LocalExplanationGenerator
from xpshacl_architecture import ExplanationOutput, ConstraintViolation
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
    parser.add_argument("-d", "--data", required=True, help="Path to the RDF data file")
    parser.add_argument("-s", "--shapes", required=True, help="Path to the SHACL shapes file")
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
    parser.add_argument(
        '-o', '--output',
        dest='output_file',  # Variable name to store the path
        type=str,
        default=None,        # Default is None, meaning no file specified
        help="Path to the file where the output report should be saved. If not specified, prints to console."
    )

    args = parser.parse_args()

    languages = [lang.strip() for lang in args.language.lower().split(',')]

    # Load data and shapes graphs
    logger.info("Loading RDF graphs...")
    try:
        data_graph = Graph().parse(args.data, format="ttl")
        shapes_graph = Graph().parse(args.shapes, format="ttl")
    except Exception as e:
        logger.error(f"Error loading RDF graphs: {e}")
        return
    logger.info("RDF graphs loaded.")

    # Initialize components
    logger.info("Initializing components...")
    validator = ExtendedShaclValidator(shapes_graph, args.inference)
    justification_builder = JustificationTreeBuilder(data_graph, shapes_graph)
    context_retriever = ContextRetriever(data_graph, shapes_graph)
    violation_kg = ViolationKnowledgeGraph() # KG is loaded during init

    if args.local:
        explanation_generator = LocalExplanationGenerator()
    else:
        explanation_generator = ExplanationGenerator(args.model)
    logger.info("Components initialized.")

    # Validate
    logger.info("Starting SHACL validation...")
    validation_start_time = time.time()
    is_valid, validation_graph, violations = validator.validate(data_graph)
    validation_end_time = time.time()
    logger.info(f"Validation finished in {validation_end_time - validation_start_time:.4f} seconds. Found {len(violations)} violations.")

    if not violations:
        logger.info("Validation successful. No violations found.")
        end_time = time.time()
        logger.info(f"Total execution time: {end_time - start_time:.4f} seconds")
        return

    # --- Process Violations by Signature ---
    logger.info("Grouping violations by signature...")
    violations_by_signature = {}
    for violation in violations:
        try:
            signature = create_violation_signature(violation)
            if signature not in violations_by_signature:
                violations_by_signature[signature] = []
            violations_by_signature[signature].append(violation)
        except Exception as e:
            logger.error(f"Error creating signature for violation {violation}: {e}")
            # Decide how to handle signature creation errors, e.g., skip violation
            continue
    logger.info(f"Found {len(violations_by_signature)} unique violation signatures.")


    explanations_by_signature = {} # Cache explanations generated/retrieved in this run
    processed_signatures = 0
    total_signatures = len(violations_by_signature)

    logger.info("Processing unique violation signatures...")
    for signature, representative_violations in violations_by_signature.items():
        processed_signatures += 1
        logger.info(f"Processing signature {processed_signatures}/{total_signatures}: {signature}")

        if not representative_violations: continue
        representative_violation = representative_violations[0] # Use the first instance

        # --- Perform expensive operations ONCE per signature ---
        logger.debug(f"Building justification for signature: {signature}")
        jt = justification_builder.build_justification_tree(representative_violation)

        logger.debug(f"Retrieving context for signature: {signature}")
        context = context_retriever.retrieve_context(representative_violation)
        # -------------------------------------------------------

        language_explanations = {} # Holds ExplanationOutput objects for this signature
        languages_to_generate = []

        # 1. Check KG cache for each requested language
        logger.debug(f"Checking KG cache for signature: {signature}")
        for lang in languages:
            cached_explanation_output = violation_kg.get_explanation(signature, lang) # Expects ExplanationOutput or None
            if cached_explanation_output:
                logger.debug(f"Cache hit for signature {signature}, lang {lang}.")
                language_explanations[lang] = cached_explanation_output
            else:
                logger.debug(f"Cache miss for signature {signature}, lang {lang}.")
                languages_to_generate.append(lang)

        # 2. Generate missing explanations using the LLM
        if languages_to_generate:
            logger.info(f"Generating explanations via LLM for signature {signature}, languages: {languages_to_generate}")
            # llm_output format: Dict[str, Tuple[str, str]] -> {lang: (nlt, cs_string)}
            llm_output = explanation_generator.generate_explanation_output(
                representative_violation, jt, context, languages_to_generate
            )

            # 3. Store the newly generated explanations in the KG (in memory)
            for lang, (nlt, cs_string) in llm_output.items():
                explanation = ExplanationOutput(
                    natural_language_explanation=nlt,
                    correction_suggestions=cs_string, # Store the combined string
                    violation=representative_violation, # Associate with the representative violation
                    justification_tree=jt,
                    retrieved_context=context,
                    provided_by_model=explanation_generator.model_name, # Assuming local has model_name too
                )
                # Add to KG in memory (DOES NOT SAVE TO DISK)
                violation_kg.add_violation(signature, explanation, lang)
                language_explanations[lang] = explanation # Store the ExplanationOutput object locally

        # Store the ExplanationOutput objects for this signature (keyed by lang)
        explanations_by_signature[signature] = language_explanations

    # --- Save the Violation KG *once* after processing all signatures ---
    logger.info("Saving Violation Knowledge Graph...")
    violation_kg.save_kg()
    logger.info("Violation Knowledge Graph saved.")

    # --- Reconstruct Final Output ---
    # Create the final list, associating each original violation instance
    # with the explanation corresponding to its signature.
    logger.info("Reconstructing final output...")
    final_explanations_output = []
    for violation in violations:
         try:
             signature = create_violation_signature(violation)
             explanation_map_for_sig = explanations_by_signature.get(signature) # Get the dict {lang: ExplanationOutput}

             if explanation_map_for_sig:
                 # Convert ExplanationOutput objects to dicts for JSON output
                 explanation_details_dict = {
                     lang: expl_output.to_dict()
                     for lang, expl_output in explanation_map_for_sig.items()
                 }
                 output_entry = {
                     # Optionally include violation instance details if needed, useful for debugging
                     # "violation_instance": violation.to_dict(),
                     "focus_node": violation.focus_node, # Minimal info to identify the instance
                     "explanation": explanation_details_dict # Contains NLT, CS, context etc. per lang
                 }
                 final_explanations_output.append(output_entry)
             else:
                 logger.warning(f"Could not find explanation for signature {signature} derived from violation {violation.focus_node}. Skipping in final output.")

         except Exception as e:
             logger.error(f"Error reconstructing output for violation {violation}: {e}")
             # Decide how to handle reconstruction errors

    logger.info("Final output reconstructed.")

    final_output_string = json.dumps(final_explanations_output, indent=2, default=str)

    if args.output_file:
        # Output file was specified
        try:
            with open(args.output_file, 'w', encoding='utf-8') as f:
                f.write(final_output_string)
            logger.info(f"Output successfully written to: {args.output_file}")
        except IOError as e:
            logger.error(f"Error writing to output file {args.output_file}: {e}")
            logger.info("\n--- Outputting to Console due to File Error ---")
            logger.info(final_output_string)
    else:
        # No output file specified, log to console
        logger.info(final_output_string)
    

    end_time = time.time()  # Record the end time
    elapsed_time = end_time - start_time  # Calculate the elapsed time

    logger.info(f"Total execution time: {elapsed_time:.4f} seconds")
    logger.info("xpSHACL processing completed.")

if __name__ == "__main__":
    main()