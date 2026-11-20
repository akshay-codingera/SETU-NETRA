import os, glob

def check_files():
    print("--- INGESTION / BENCHMARK FILES ---")
    patterns = [
        "sample_data/*",
        "tests/fixtures/image_pipeline/*",
        "output/uploads/**/*",
        "output/e2e_verify/*",
        "benchmarks/v1_1/corpus/*",
        "benchmarks/datasets/*",
        "reports/screenshots/*"
    ]
    for pat in patterns:
        files = glob.glob(pat, recursive=True)
        for f in files:
            if os.path.isfile(f):
                print(f"{f} | {os.path.getsize(f)} bytes")

check_files()
