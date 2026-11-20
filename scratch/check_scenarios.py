import json

with open('tests/fixtures/image_pipeline/test_results_summary.json', 'r') as f:
    scenarios = json.load(f)

for s in scenarios:
    print(f"Scenario {s.get('scenario')}: {s.get('name')} | Format: {s.get('format')} | Domain: {s.get('domain')} | Status: {s.get('status')}")
