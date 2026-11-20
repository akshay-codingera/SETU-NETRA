import json

files_to_check = [
    'sample_data/development_calibration_dataset.json',
    'sample_data/evaluation_benchmark.json',
    'benchmarks/datasets/qa_eval_dataset.json',
    'benchmarks/datasets/routing_eval_dataset.json',
    'tests/fixtures/image_pipeline/test_results_summary.json'
]

for f in files_to_check:
    print(f"\n==========================================")
    print(f"FILE: {f}")
    print(f"==========================================")
    try:
        with open(f, 'r', encoding='utf-8') as fp:
            data = json.load(fp)
            if isinstance(data, list):
                print(f"Type: list of {len(data)} items")
                if len(data) > 0:
                    print("First item keys/sample:")
                    print(json.dumps(data[0], indent=2)[:300])
            elif isinstance(data, dict):
                print(f"Type: dict with keys: {list(data.keys())}")
                first_key = list(data.keys())[0]
                print(f"Sample under '{first_key}':")
                print(str(data[first_key])[:300])
    except Exception as e:
        print(f"Error reading {f}: {e}")
