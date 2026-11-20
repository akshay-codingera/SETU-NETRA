"""
audit_priority2_cloud_providers.py: Verification of Cloud Provider status and categorization.

Audits:
- GeminiCloudAdapter
- GroqCloudAdapter
- OpenRouterCloudAdapter

Categorization criteria:
- NOT_CONFIGURED: API key missing/empty. No network connection possible.
- CONFIGURED: Non-empty API key provided in settings or env, but no live connection probe verified.
- CONNECTED: Health-check / endpoint probe confirmed reachable with valid credentials (HTTP 200).
- INFERENCE_VERIFIED: Full inference round-trip executed with valid response payload parsed.
"""

import os
import sys
import json
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.routing.adapters.cloud_adapters import (
    GeminiCloudAdapter,
    GroqCloudAdapter,
    OpenRouterCloudAdapter,
)
from setu_netra.core.config import get_api_key, is_local_only, set_local_only

def audit_cloud_providers():
    print("=" * 80)
    print("PRIORITY 2: CLOUD PROVIDER RUNTIME VALIDATION")
    print("=" * 80)

    providers = {
        "gemini": GeminiCloudAdapter(),
        "groq": GroqCloudAdapter(),
        "openrouter": OpenRouterCloudAdapter(),
    }

    env_vars = {
        "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
        "groq": ["GROQ_API_KEY"],
        "openrouter": ["OPENROUTER_API_KEY"],
    }

    audit_records = {}

    for name, adapter in providers.items():
        print(f"\n--- Provider: {name.upper()} ---")
        adapter_status = adapter.status
        is_avail = adapter.is_available()
        cred = adapter._get_credential()

        # Check environment variables
        env_found = any(bool(os.environ.get(v)) for v in env_vars[name])
        print(f"Environment keys present: {env_found}")
        print(f"Adapter reported status: {adapter_status}")
        print(f"Adapter is_available(): {is_avail}")
        print(f"Has credential: {bool(cred)}")

        # Exact categorization
        if not cred:
            classification = "NOT_CONFIGURED"
            evidence = "No API key configured in environment or application settings."
            live_verified = False
        else:
            classification = "CONFIGURED"
            evidence = "API key string detected, but live completion inference not confirmed."
            live_verified = False

        print(f"Independent Classification: {classification}")
        print(f"Live Inference Verified: {live_verified}")
        print(f"Evidence Note: {evidence}")

        audit_records[name] = {
            "adapter_reported_status": adapter_status,
            "is_available": is_avail,
            "has_credential": bool(cred),
            "classification": classification,
            "inference_verified": live_verified,
            "evidence": evidence,
        }

    # Verify no credentials leaked into git or files
    print("\n--- Credential Leak Audit ---")
    sensitive_keys = ["AIzaSy", "gsk_", "sk-or-v1-"]
    leaks_found = []
    for root, _, files in os.walk("src"):
        for file in files:
            if file.endswith(".py"):
                fpath = Path(root) / file
                content = fpath.read_text(encoding="utf-8", errors="ignore")
                for s in sensitive_keys:
                    if s in content:
                        leaks_found.append(f"{fpath}: contains '{s}'")
    
    print(f"Source code credential leaks found: {len(leaks_found)}")
    if leaks_found:
        print("LEAKS DETECTED:", leaks_found)
    else:
        print("CONFIRMED: Zero credentials or secret tokens found in source code.")

    audit_records["credential_leak_audit"] = {
        "leaks_detected": len(leaks_found),
        "zero_leaks_confirmed": len(leaks_found) == 0,
    }

    print("\n" + "=" * 80)
    print("PRIORITY 2 AUDIT COMPLETE")
    print("=" * 80)

    with open("output/priority2_audit_results.json", "w") as f:
        json.dump(audit_records, f, indent=2)

    return audit_records

if __name__ == "__main__":
    audit_cloud_providers()
