import subprocess
import time
import argparse

def run_main_and_get_time(data_path, shapes_path, model):
    command = [
        "python3.13.exe",
        "-m"
        "pyshacl",
        "-s",
        data_path,
        "-f",
        "human",
        shapes_path
    ]
    start_time = time.time()
    subprocess.run(command, capture_output=True, text=True)
    end_time = time.time()
    execution_time = end_time - start_time
    return f"{execution_time:.7f}"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run main.py multiple times and measure execution time.")
    parser.add_argument("-n", type=int, default=10, help="Number of times to run the main script.")
    args = parser.parse_args()

    num_runs = args.n
    data_path = ".\\data\\complex_data.ttl"
    shapes_path = ".\\data\\complex_shapes.ttl"
    model = "gpt-4o-mini-2024-07-18"

    for i in range(num_runs):
        execution_time = run_main_and_get_time(data_path, shapes_path, model)
        print("Run #" + str(i + 1) + ": " + str(execution_time))
