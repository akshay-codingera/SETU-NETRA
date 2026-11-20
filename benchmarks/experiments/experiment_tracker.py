"""
experiment_tracker.py: Experiment metadata and artifact tracking subsystem for SETU-NETRA.

Why this file exists:
Ensures all benchmark experiments are accompanied by immutable provenance metadata:
- ISO 8601 Timestamp
- Git commit hash or source version
- Hardware details (CPU model, cores, physical RAM)
- Operating system platform and version
- Python interpreter and environment version
- Model identifiers and configurations
- Scheduler configurations
- Dataset / workload identifier
- Number of requests, warm-up count, and repetition count
Persists structured raw and aggregated JSON artifacts under benchmarks/results/.
"""

import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from setu_netra.routing.system_telemetry import get_system_telemetry


def get_git_revision() -> str:
    """Attempt to retrieve git HEAD commit hash, or return fallback."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            timeout=2.0,
        )
        return out.decode("utf-8").strip()
    except Exception:
        return "stage6-experimental-validation"


def get_hardware_environment_metadata() -> Dict[str, Any]:
    """Capture host system architecture, CPU info, and total physical memory."""
    sys_tel = get_system_telemetry()
    return {
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count_logical": os.cpu_count() or 1,
        "total_ram_mb": sys_tel.total_ram_mb,
        "python_version": sys.version.split()[0],
        "python_executable": sys.executable,
    }


@dataclass
class ExperimentMetadata:
    """Immutable envelope accompanying every benchmark experiment run."""
    experiment_id: str
    suite_name: str
    description: str
    timestamp_iso: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    git_commit: str = field(default_factory=get_git_revision)
    hardware: Dict[str, Any] = field(default_factory=get_hardware_environment_metadata)
    model_configs: Dict[str, Any] = field(default_factory=dict)
    scheduler_configs: Dict[str, Any] = field(default_factory=dict)
    workload_id: str = "default"
    total_requests: int = 0
    warmup_count: int = 0
    repetition_count: int = 1
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ExperimentTracker:
    """Manages recording, serializing, and persisting benchmark results."""

    def __init__(self, base_dir: Optional[Path] = None):
        self._base_dir = base_dir or (Path(__file__).resolve().parent.parent / "results")
        self._raw_dir = self._base_dir / "raw"
        self._agg_dir = self._base_dir / "aggregated"
        self._charts_dir = self._base_dir / "charts"

        self._raw_dir.mkdir(parents=True, exist_ok=True)
        self._agg_dir.mkdir(parents=True, exist_ok=True)
        self._charts_dir.mkdir(parents=True, exist_ok=True)

    @property
    def raw_dir(self) -> Path:
        return self._raw_dir

    @property
    def aggregated_dir(self) -> Path:
        return self._agg_dir

    @property
    def charts_dir(self) -> Path:
        return self._charts_dir

    def save_raw_experiment_data(
        self,
        experiment_id: str,
        metadata: ExperimentMetadata,
        raw_measurements: List[Dict[str, Any]],
    ) -> Path:
        """Persist detailed per-request timing and execution traces."""
        filename = f"{experiment_id}_raw.json"
        dest_path = self._raw_dir / filename
        payload = {
            "metadata": metadata.to_dict(),
            "raw_measurements": raw_measurements,
        }
        with open(dest_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return dest_path

    def save_aggregated_results(
        self,
        experiment_id: str,
        metadata: ExperimentMetadata,
        aggregated_metrics: Dict[str, Any],
    ) -> Path:
        """Persist aggregated statistics, percentiles, and confusion matrices."""
        filename = f"{experiment_id}_summary.json"
        dest_path = self._agg_dir / filename
        payload = {
            "metadata": metadata.to_dict(),
            "metrics": aggregated_metrics,
        }
        with open(dest_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return dest_path
