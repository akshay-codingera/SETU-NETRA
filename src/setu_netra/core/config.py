"""
config.py: Global system configuration, privacy controls, and API credential management.

Why this file exists:
Centralizes runtime configuration, local-only privacy toggles, and safe provider credential
storage. Guarantees that cloud API keys are never hardcoded or leaked in logs or UI responses.
"""

import os
import threading
from typing import Any, Dict, Optional

_LOCK = threading.RLock()

# Default to Local-Only mode (1/true) for strict data privacy unless explicitly changed
_LOCAL_ONLY_DEFAULT = os.environ.get("SETU_LOCAL_ONLY", "1").lower() in ("1", "true", "yes")

_SETTINGS: Dict[str, Any] = {
    "local_only": _LOCAL_ONLY_DEFAULT,
    "active_scheduler": "AdaptiveResilientScheduler",
    "preferred_local_model": "grounded-extractive-qa-v1",
    "cloud_consent_given": False,
    "api_keys": {
        "gemini": os.environ.get("GEMINI_API_KEY", ""),
        "groq": os.environ.get("GROQ_API_KEY", ""),
        "openrouter": os.environ.get("OPENROUTER_API_KEY", ""),
    },
    "enabled_providers": {
        "native": True,
        "huggingface": True,
        "ollama": True,
        "gemini": True,
        "groq": True,
        "openrouter": True,
    },
}


def is_local_only() -> bool:
    """Check if Local-Only Privacy Mode is strictly active."""
    with _LOCK:
        return _SETTINGS["local_only"]


def set_local_only(enabled: bool) -> None:
    """Toggle Local-Only Privacy Mode."""
    with _LOCK:
        _SETTINGS["local_only"] = bool(enabled)


def get_api_key(provider: str) -> Optional[str]:
    """Retrieve credential for a given cloud provider."""
    with _LOCK:
        key = _SETTINGS["api_keys"].get(provider.lower())
        if not key:
            env_var = f"{provider.upper()}_API_KEY"
            key = os.environ.get(env_var, "")
        return key if key else None


def set_api_key(provider: str, key: str) -> None:
    """Set credential in memory for a cloud provider."""
    with _LOCK:
        _SETTINGS["api_keys"][provider.lower()] = key.strip()


def is_provider_enabled(provider: str) -> bool:
    """Check if a model provider is administratively enabled."""
    with _LOCK:
        return _SETTINGS["enabled_providers"].get(provider.lower(), True)


def set_provider_enabled(provider: str, enabled: bool) -> None:
    """Enable or disable a model provider."""
    with _LOCK:
        _SETTINGS["enabled_providers"][provider.lower()] = bool(enabled)


def get_preferred_local_model() -> str:
    with _LOCK:
        return _SETTINGS["preferred_local_model"]


def set_preferred_local_model(model_id: str) -> None:
    with _LOCK:
        _SETTINGS["preferred_local_model"] = model_id


def get_system_settings_view() -> Dict[str, Any]:
    """Return a sanitized view of system settings (masks API keys)."""
    with _LOCK:
        masked_keys = {}
        for prov, key in _SETTINGS["api_keys"].items():
            if key:
                masked_keys[prov] = f"{key[:4]}****{key[-4:]}" if len(key) > 8 else "********"
            else:
                masked_keys[prov] = ""

        return {
            "local_only": _SETTINGS["local_only"],
            "active_scheduler": _SETTINGS["active_scheduler"],
            "preferred_local_model": _SETTINGS["preferred_local_model"],
            "cloud_consent_given": _SETTINGS["cloud_consent_given"],
            "configured_providers": {
                prov: bool(key) for prov, key in _SETTINGS["api_keys"].items()
            },
            "enabled_providers": dict(_SETTINGS["enabled_providers"]),
            "api_keys_masked": masked_keys,
        }
