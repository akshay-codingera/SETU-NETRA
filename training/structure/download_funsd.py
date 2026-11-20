import urllib.request
import zipfile
import os
import sys

URL = "https://guillaumejaume.github.io/FUNSD/dataset.zip"
TARGET_ZIP = "training/datasets/SETU-SR/FUNSD/dataset.zip"
EXTRACT_DIR = "training/datasets/SETU-SR/FUNSD/raw"

print(f"Downloading FUNSD from {URL}...")
req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req) as resp, open(TARGET_ZIP, "wb") as out_file:
    total_size = int(resp.headers.get("Content-Length", 0))
    downloaded = 0
    chunk_size = 1024 * 256
    while True:
        chunk = resp.read(chunk_size)
        if not chunk:
            break
        out_file.write(chunk)
        downloaded += len(chunk)
        if total_size > 0:
            percent = downloaded / total_size * 100
            sys.stdout.write(f"\rDownloaded {downloaded}/{total_size} bytes ({percent:.1f}%)")
            sys.stdout.flush()

print(f"\nDownload complete: {TARGET_ZIP} ({os.path.getsize(TARGET_ZIP)} bytes)")
print("Extracting FUNSD...")
with zipfile.ZipFile(TARGET_ZIP, "r") as z:
    z.extractall(EXTRACT_DIR)
print(f"Extraction complete into {EXTRACT_DIR}")

# Cleanup zip file to keep repository clean
if os.path.exists(TARGET_ZIP):
    os.remove(TARGET_ZIP)
    print("Cleaned up temporary zip file.")
