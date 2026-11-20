import os

extensions = ('.pdf', '.docx', '.png', '.jpg', '.jpeg', '.json', '.txt')
exclude_dirs = {'.venv', 'node_modules', '.git', '.gemini'}

results = []
for root, dirs, files in os.walk('.'):
    # filter dirs
    dirs[:] = [d for d in dirs if d not in exclude_dirs]
    for f in files:
        if f.lower().endswith(extensions):
            full_path = os.path.join(root, f)
            size = os.path.getsize(full_path)
            results.append((full_path, size))

print(f"Total relevant files found: {len(results)}")
by_ext = {}
for p, s in results:
    ext = os.path.splitext(p)[1].lower()
    by_ext.setdefault(ext, []).append((p, s))

for ext, flist in by_ext.items():
    print(f"\n--- Extension {ext} ({len(flist)} files) ---")
    for p, s in flist[:25]:
        print(f"  {p} ({s} bytes)")
    if len(flist) > 25:
        print(f"  ... and {len(flist)-25} more")
