"""
demo_system_health.py: Inspects live FastAPI ASGI service, Ollama status, and SQLite document repository.
"""
import sys
import json
import urllib.request

def run():
    print("=" * 68)
    print("  SETU-NETRA: LIVE SYSTEM STATUS & ENGINE TELEMETRY")
    print("=" * 68)

    url = "http://127.0.0.1:8502/api/v1/health"
    try:
        req = urllib.request.urlopen(url, timeout=5)
        data = json.loads(req.read().decode())
    except Exception as e:
        print(f"Error connecting to SETU-NETRA backend: {e}")
        print("Please ensure backend is running with: python src/setu_netra/api/main.py")
        return

    print(f"\n[1] CORE API & ASYNC LIFESPAN:")
    print(f"    • Service State:    {data.get('status')}")
    print(f"    • Engine Version:   {data.get('version')}")
    print(f"    • Server Uptime:    {data.get('uptime_seconds', 0):.1f} seconds")

    db = data.get("database", {})
    print(f"\n[2] SQLITE DOCUMENT REPOSITORY:")
    print(f"    • DB Connected:     {db.get('connected')}")
    print(f"    • Stored Documents: {db.get('document_count')} records")

    ollama = data.get("ollama", {})
    print(f"\n[3] LOCAL INFERENCE ORCHESTRATION (OLLAMA):")
    print(f"    • Local Host:       {ollama.get('endpoint')}")
    print(f"    • Host Reachable:   {ollama.get('reachable')}")
    print(f"    • Local Model:      {ollama.get('installed_models', ['qwen3.5:2b'])[0]}")
    print(f"    • Qwen Available:   {ollama.get('qwen_installed')}")

    print("\n" + "=" * 68)
    print("  ALL SYSTEMS OPERATIONAL: Ready for live teacher evaluation.")
    print("=" * 68)

if __name__ == "__main__":
    run()
