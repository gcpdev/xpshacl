import requests, json, time, logging
import os
from io import BytesIO
from rdflib import Graph, RDF, RDFS, OWL
from rdflib.namespace import Namespace
from rdflib.plugins.sparql import prepareQuery
from urllib.parse import urlparse
from pyshacl import validate

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

repository_address = "http://lov.okfn.org/dataset/lov/api/v2/vocabulary/list"
ontologies_urls = []
outdir = "./shark_results"  # Replace with your desired output directory

def parse():
    """Parses the JSON file."""
    try:
        response = requests.get(repository_address)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        root = response.json()

        for item in root:
            ontologies_urls.append(item["uri"])

        logger.info(f"Found {len(ontologies_urls)} ontologies URLs.")

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching or parsing JSON: {e}")
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON: {e}")

def get_stream(download_url):
    """Opens a connection and returns the stream."""
    try:
        response = requests.get(download_url, headers={"Content-type": "application/rdf+xml", "Accept": "application/rdf+xml"}, timeout=2)
        response.raise_for_status()

        # Handle redirects (301, 302, 303)
        if response.status_code in [301, 302, 303]:
            location = response.headers.get("Location")
            if location:
                if location.startswith("https://"):
                    response = requests.get(location, headers={"Content-type": "application/rdf+xml", "Accept": "application/rdf+xml"}, timeout=2)
                    response.raise_for_status()
                elif response.status_code == 303:
                    new_url = download_url.replace("http://", "https://")
                    response = requests.get(new_url, headers={"Content-type": "application/rdf+xml", "Accept": "application/rdf+xml"}, timeout=2)
                    response.raise_for_status()

        return BytesIO(response.content)

    except requests.exceptions.RequestException as e:
        raise Exception(f"Error fetching URL: {e}")

def stream_and_run_tests(urls):
    """Streams ontologies from URLs and runs tests against them."""

    os.makedirs(outdir, exist_ok=True)
    fw_output = "ontology;size;test;fail\n"

    try:
        with open("shark_shapes.ttl", "r") as f:
            test = f.read()
    except FileNotFoundError:
        logger.error("shark_shapes.ttl file not found.")
        return

    success = 0
    fail = 0
    tested = 0

    for url in urls:
        tested = tested + 1
        model = None

        logger.info(f"Streaming {url}")

        try:
            ontology = get_stream(url)
            if ontology:
                logger.info(f"{url} successfully read")
                if url in ["http://ns.inria.fr/emoca", "http://purl.org/limo-ontology/limo/", "http://linkedscience.org/lsc/ns#", "https://talespaiva.github.io/step/"]:
                    fail = fail + 1
                    continue  # skip broken ontologies
                try:
                    g = Graph()
                    g.parse(ontology, format="xml")
                    model = g
                except Exception as e:
                    fail = fail + 1
                    logger.error(f"Error parsing {url}: {e}")
                    continue
                if len(model) == 0:
                    logger.error(f"{url} has {len(model)} elements. Skipping it...")
                    fail = fail + 1
                    continue
                logger.info(f"{url} has {len(model)} elements")
                logger.info(f"Running tests on {url}")

                try:
                    # Implement your SHACL test execution logic here
                    conforms, results_graph, results_text = validate(
                        data_graph=model,
                        shacl_graph=test,
                        data_graph_format="xml",
                        shacl_graph_format="ttl",
                        inference='rdfs',
                        debug=False,
                        serialize_report_graph="ttl",
                    )

                    test_map = {}
                    if not conforms:
                        results_graph_parsed = Graph().parse(data=results_graph, format="turtle")
                        for s, p, o in results_graph_parsed.triples((None, RDF.type, Namespace("http://www.w3.org/ns/shacl#").ValidationResult)):
                            message = str(results_graph_parsed.value(s, Namespace("http://www.w3.org/ns/shacl#").resultMessage))
                            if message in test_map:
                                test_map[message] += 1
                            else:
                                test_map[message] = 1

                    for message, count in test_map.items():
                        fw_output += f"{url};{len(model)};{message};{count}\n"

                    success = success + 1
                except Exception as e:
                    logger.error(f"Error running SHACL tests on {url}: {e}")
                    fail +=1
            else:
                logger.error(f"{url} could not be read. Skipping it...")
                fail = fail + 1
        except Exception as e:
            logger.error(f"Error processing {url}: {e}")
            fail = fail + 1

    with open(os.path.join(outdir, "results_daniel.csv"), "w") as fw:
        fw.write(fw_output)

    logger.info(f"tested: {tested}")
    logger.info(f"success: {success}")
    logger.info(f"failed: {fail}")

if __name__ == "__main__":
    start_time = time.time()  # Record the start time
    os.makedirs(outdir, exist_ok=True)
    logger.info("Checking the LOV cloud...")
    parse()
    logger.info("Starting tests...")
    stream_and_run_tests(ontologies_urls)
    end_time = time.time()  # Record the end time
    elapsed_time = end_time - start_time  # Calculate the elapsed time

    logger.info(f"Total execution time: {elapsed_time:.4f} seconds")  # Log the elapsed time
    print(f"Total execution time: {elapsed_time:.4f} seconds")  # Print the elapsed time
