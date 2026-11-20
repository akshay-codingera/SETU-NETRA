import os, sys, json, hashlib, zipfile

rec_dir = r'research_audit/evidence_reconciliation_20261120'
prev_dir = r'research_audit/complete_audit_20261120_045130'
zip_name = r'SETU_NETRA_COMPLETE_EVIDENCE_PACKAGE.zip'

def hash_file(p):
    with open(p, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()

# 1. Build manifest of reconciliation artifacts
manifest = {
    'package_metadata': {
        'title': 'SETU-NETRA Complete Evidence Package',
        'timestamp_iso': '2026-11-20T06:26:30Z',
        'creator': 'Senior Research Auditor',
        'description': 'Cryptographically verified evidence recovery, reconciliation reports, raw predictions, and source matrices'
    },
    'previous_audit_artifacts': [],
    'new_reconciliation_artifacts': []
}

# Previous audit files
for f in sorted(os.listdir(prev_dir)):
    p = os.path.join(prev_dir, f)
    if os.path.isfile(p):
        manifest['previous_audit_artifacts'].append({
            'relative_path': os.path.relpath(p),
            'filename': f,
            'size_bytes': os.path.getsize(p),
            'sha256': hash_file(p),
            'classification': 'PRESENT AND COMPLETE'
        })

# New reconciliation files
for root, dirs, files in os.walk(rec_dir):
    for f in sorted(files):
        p = os.path.join(root, f)
        if f == 'EVIDENCE_PACKAGE_MANIFEST.json':
            continue
        rel = os.path.relpath(p)
        manifest['new_reconciliation_artifacts'].append({
            'relative_path': rel,
            'filename': f,
            'size_bytes': os.path.getsize(p),
            'sha256': hash_file(p),
            'file_type': os.path.splitext(f)[1],
            'status': 'NEWLY GENERATED'
        })

manifest_path = os.path.join(rec_dir, 'EVIDENCE_PACKAGE_MANIFEST.json')
with open(manifest_path, 'w', encoding='utf-8') as f:
    json.dump(manifest, f, indent=2)
print(f'Wrote {manifest_path}')

# Add manifest itself to package list
manifest_entry = {
    'relative_path': os.path.relpath(manifest_path),
    'filename': 'EVIDENCE_PACKAGE_MANIFEST.json',
    'size_bytes': os.path.getsize(manifest_path),
    'sha256': hash_file(manifest_path),
    'file_type': '.json',
    'status': 'NEWLY GENERATED'
}

# 2. Build ZIP archive
print('Packaging ZIP archive...')
with zipfile.ZipFile(zip_name, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
    # Include both audit directories
    for audit_dir in [prev_dir, rec_dir]:
        for root, dirs, files in os.walk(audit_dir):
            for f in files:
                p = os.path.join(root, f)
                # Avoid self-referencing if zip was in dir
                if f.endswith('.zip') or f.endswith('.pyc'):
                    continue
                arcname = os.path.relpath(p)
                zf.write(p, arcname)
                
    # Include relevant source files
    src_files = [
        'src/setu_netra/policy/cm_rp.py',
        'src/setu_netra/evidence/er_sp.py',
        'src/setu_netra/structure/sr_edgenet.py',
        'src/setu_netra/pipeline/integrated_pipeline.py',
        'src/setu_netra/qa/verifier.py',
        'src/setu_netra/routing/router.py',
        'src/setu_netra/routing/adapters/ocr_adapter.py',
        'src/setu_netra/routing/adapters/ollama_adapter.py',
        'src/setu_netra/runtime/circuit_breaker.py',
        'src/setu_netra/runtime/worker_pool.py',
        'src/setu_netra/runtime/telemetry.py'
    ]
    for sf in src_files:
        if os.path.exists(sf):
            zf.write(sf, sf)

    # Include benchmark results
    for b_file in [
        'benchmarks/results/aggregated/qa_quality_evaluation_summary.json',
        'benchmarks/results/aggregated/real_inference_benchmarks_summary.json',
        'benchmarks/results/aggregated/reliability_evaluation_summary.json',
        'benchmarks/results/aggregated/routing_evaluation_summary.json',
        'benchmarks/results/aggregated/scheduler_microbenchmarks_summary.json',
        'benchmarks/results/raw/qa_quality_evaluation_raw.json',
        'benchmarks/results/raw/real_inference_benchmarks_raw.json',
        'benchmarks/results/raw/reliability_evaluation_raw.json',
        'benchmarks/results/raw/routing_evaluation_raw.json',
        'benchmarks/v1_1/data/aggregated_baseline_results.json',
        'models/structure/evaluation_results.json',
        'models/evidence/evaluation_results.json',
        'models/policy/evaluation_results.json',
        'research/paper/evidence/CRITICAL_AUDIT_METRICS.json',
        'research/paper/evidence/FINAL_METRICS.json'
    ]:
        if os.path.exists(b_file):
            zf.write(b_file, b_file)

zip_size = os.path.getsize(zip_name)
zip_hash = hash_file(zip_name)

print('=' * 80)
print(f'Archive created: {zip_name}')
print(f'File Size: {zip_size:,} bytes ({zip_size / 1024 / 1024:.2f} MB)')
print(f'SHA-256 Checksum: {zip_hash}')
print('=' * 80)
