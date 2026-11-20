"""
system_telemetry.py: Genuine host hardware telemetry abstraction for SETU-NETRA.

Why this file exists:
Provides a platform-independent, thread-safe hardware resource telemetry layer.
Gathers real CPU utilization and physical RAM metrics directly from the host operating
system kernel via Windows API (ctypes) or Linux /proc virtual filesystem.
Adheres strictly to zero-simulation mandates and explicitly signals invalid or
stale measurements.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import logging
import os
import platform
import sys
import threading
import time
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class SystemTelemetry:
    """Snapshot of host hardware utilization with validity indicators."""
    cpu_percent: float                         # 0.0 to 100.0%
    ram_percent: float                         # 0.0 to 100.0%
    avail_ram_mb: float                        # Available physical RAM in MB
    total_ram_mb: float                        # Total physical RAM in MB
    timestamp: float                           # Wall-clock timestamp (time.time())
    is_real: bool = True                       # True if measured from real OS; False if fallback
    is_valid: bool = True                      # True if measurement succeeded without error
    error_message: Optional[str] = None        # Diagnostic error string if is_valid is False
    platform_name: str = field(default_factory=platform.system)

    def is_stale(self, max_age_sec: float = 5.0) -> bool:
        """Check if telemetry reading is older than staleness threshold."""
        return (time.time() - self.timestamp) > max_age_sec


# Windows ctypes bindings
_HAS_WINDOWS_API = False
if platform.system() == "Windows":
    try:
        import ctypes

        class _MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        class _FILETIME(ctypes.Structure):
            _fields_ = [
                ("dwLowDateTime", ctypes.c_ulong),
                ("dwHighDateTime", ctypes.c_ulong),
            ]

        _HAS_WINDOWS_API = True
        _kernel32 = ctypes.windll.kernel32
    except Exception as err:
        logger.warning("Windows ctypes API initialization failed: %s", err)
        _HAS_WINDOWS_API = False


class BaseTelemetryProvider(ABC):
    """Abstract base provider for host telemetry with thread-safe sample caching."""

    def __init__(self, cache_ttl_sec: float = 0.5):
        self._cache_ttl = cache_ttl_sec
        self._lock = threading.Lock()
        self._last_sample: Optional[SystemTelemetry] = None

    @abstractmethod
    def sample_telemetry(self) -> SystemTelemetry:
        """Perform a single raw hardware sample from the operating system."""
        pass

    def get_telemetry(self) -> SystemTelemetry:
        """Sample host CPU and memory with thread-safe rate-limiting cache."""
        now = time.time()
        with self._lock:
            if self._last_sample is not None and (now - self._last_sample.timestamp) < self._cache_ttl:
                return self._last_sample

            sample = self.sample_telemetry()
            self._last_sample = sample
            return sample


class WindowsTelemetryProvider(BaseTelemetryProvider):
    """Windows kernel telemetry provider using ctypes Win32 API bindings."""

    def __init__(self, cache_ttl_sec: float = 0.5):
        super().__init__(cache_ttl_sec=cache_ttl_sec)
        self._last_cpu_sample_time: float = 0.0
        self._last_idle_time: int = 0
        self._last_total_time: int = 0

        if _HAS_WINDOWS_API:
            self._last_idle_time, self._last_total_time = self._read_windows_cpu_times()
            self._last_cpu_sample_time = time.time()

    def _read_windows_cpu_times(self) -> Tuple[int, int]:
        if not _HAS_WINDOWS_API:
            return 0, 1
        idle = _FILETIME()
        kernel = _FILETIME()
        user = _FILETIME()
        if not _kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
            return 0, 1
        i = (idle.dwHighDateTime << 32) + idle.dwLowDateTime
        k = (kernel.dwHighDateTime << 32) + kernel.dwLowDateTime
        u = (user.dwHighDateTime << 32) + user.dwLowDateTime
        return i, k + u

    def sample_telemetry(self) -> SystemTelemetry:
        now = time.time()
        if not _HAS_WINDOWS_API:
            return SystemTelemetry(
                cpu_percent=0.0,
                ram_percent=0.0,
                avail_ram_mb=0.0,
                total_ram_mb=0.0,
                timestamp=now,
                is_real=False,
                is_valid=False,
                error_message="Windows API ctypes bindings unavailable.",
                platform_name="Windows",
            )

        # 1. Physical RAM measurement
        stat = _MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
        if not _kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            return SystemTelemetry(
                cpu_percent=0.0,
                ram_percent=0.0,
                avail_ram_mb=0.0,
                total_ram_mb=0.0,
                timestamp=now,
                is_real=True,
                is_valid=False,
                error_message="GlobalMemoryStatusEx call failed.",
                platform_name="Windows",
            )

        ram_pct = float(stat.dwMemoryLoad)
        avail_mb = float(stat.ullAvailPhys / (1024 * 1024))
        total_mb = float(stat.ullTotalPhys / (1024 * 1024))

        # 2. CPU utilization measurement
        i2, t2 = self._read_windows_cpu_times()
        delta_total = t2 - self._last_total_time
        delta_idle = i2 - self._last_idle_time
        cpu_pct = 0.0

        if delta_total > 0 and (now - self._last_cpu_sample_time) >= 0.04:
            ratio = 1.0 - (delta_idle / delta_total)
            cpu_pct = max(0.0, min(100.0, ratio * 100.0))
            self._last_idle_time = i2
            self._last_total_time = t2
            self._last_cpu_sample_time = now
        elif self._last_sample and self._last_sample.is_valid:
            cpu_pct = self._last_sample.cpu_percent

        return SystemTelemetry(
            cpu_percent=round(cpu_pct, 1),
            ram_percent=round(ram_pct, 1),
            avail_ram_mb=round(avail_mb, 1),
            total_ram_mb=round(total_mb, 1),
            timestamp=now,
            is_real=True,
            is_valid=True,
            platform_name="Windows",
        )


class LinuxTelemetryProvider(BaseTelemetryProvider):
    """Linux kernel telemetry provider parsing /proc/meminfo and /proc/stat."""

    def __init__(
        self,
        cache_ttl_sec: float = 0.5,
        proc_meminfo_path: str = "/proc/meminfo",
        proc_stat_path: str = "/proc/stat",
    ):
        super().__init__(cache_ttl_sec=cache_ttl_sec)
        self._proc_meminfo = proc_meminfo_path
        self._proc_stat = proc_stat_path
        self._last_cpu_sample_time: float = 0.0
        self._last_idle_time: int = 0
        self._last_total_time: int = 0

        self._last_idle_time, self._last_total_time = self._read_proc_stat()
        self._last_cpu_sample_time = time.time()

    def _read_proc_stat(self) -> Tuple[int, int]:
        """Read total and idle jiffies from /proc/stat."""
        if not os.path.exists(self._proc_stat):
            return 0, 1
        try:
            with open(self._proc_stat, "r", encoding="utf-8") as f:
                first_line = f.readline()
            parts = first_line.strip().split()
            if len(parts) >= 5 and parts[0] == "cpu":
                # user, nice, system, idle, iowait, irq, softirq, steal
                times = [int(p) for p in parts[1:]]
                idle = times[3] + (times[4] if len(times) > 4 else 0)
                total = sum(times)
                return idle, total
        except Exception as err:
            logger.warning("Failed to parse %s: %s", self._proc_stat, err)
        return 0, 1

    def _read_proc_meminfo(self) -> Tuple[float, float, float]:
        """Read total_mb, avail_mb, ram_percent from /proc/meminfo."""
        if not os.path.exists(self._proc_meminfo):
            raise FileNotFoundError(f"{self._proc_meminfo} does not exist.")

        mem_total_kb: Optional[float] = None
        mem_avail_kb: Optional[float] = None
        mem_free_kb: Optional[float] = None
        buffers_kb: Optional[float] = None
        cached_kb: Optional[float] = None

        with open(self._proc_meminfo, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(":")
                if len(parts) < 2:
                    continue
                k = parts[0].strip()
                v = parts[1].strip().split()[0]
                val = float(v)
                if k == "MemTotal":
                    mem_total_kb = val
                elif k == "MemAvailable":
                    mem_avail_kb = val
                elif k == "MemFree":
                    mem_free_kb = val
                elif k == "Buffers":
                    buffers_kb = val
                elif k == "Cached":
                    cached_kb = val

        if mem_total_kb is None or mem_total_kb <= 0:
            raise ValueError("Invalid or missing MemTotal in /proc/meminfo")

        if mem_avail_kb is None:
            # Fallback estimation if MemAvailable is not present (older kernels)
            free = mem_free_kb or 0.0
            buf = buffers_kb or 0.0
            cache = cached_kb or 0.0
            mem_avail_kb = free + buf + cache

        total_mb = mem_total_kb / 1024.0
        avail_mb = mem_avail_kb / 1024.0
        ram_pct = max(0.0, min(100.0, ((total_mb - avail_mb) / total_mb) * 100.0))
        return total_mb, avail_mb, ram_pct

    def sample_telemetry(self) -> SystemTelemetry:
        now = time.time()
        try:
            total_mb, avail_mb, ram_pct = self._read_proc_meminfo()
        except Exception as err:
            return SystemTelemetry(
                cpu_percent=0.0,
                ram_percent=0.0,
                avail_ram_mb=0.0,
                total_ram_mb=0.0,
                timestamp=now,
                is_real=True,
                is_valid=False,
                error_message=f"Linux meminfo read error: {err}",
                platform_name="Linux",
            )

        i2, t2 = self._read_proc_stat()
        delta_total = t2 - self._last_total_time
        delta_idle = i2 - self._last_idle_time
        cpu_pct = 0.0

        if delta_total > 0 and (now - self._last_cpu_sample_time) >= 0.04:
            ratio = 1.0 - (delta_idle / delta_total)
            cpu_pct = max(0.0, min(100.0, ratio * 100.0))
            self._last_idle_time = i2
            self._last_total_time = t2
            self._last_cpu_sample_time = now
        elif self._last_sample and self._last_sample.is_valid:
            cpu_pct = self._last_sample.cpu_percent

        return SystemTelemetry(
            cpu_percent=round(cpu_pct, 1),
            ram_percent=round(ram_pct, 1),
            avail_ram_mb=round(avail_mb, 1),
            total_ram_mb=round(total_mb, 1),
            timestamp=now,
            is_real=True,
            is_valid=True,
            platform_name="Linux",
        )


class UnsupportedPlatformProvider(BaseTelemetryProvider):
    """Explicit fallback provider for platforms without hardware kernel reader."""

    def __init__(self, platform_name: str = "Unknown"):
        super().__init__(cache_ttl_sec=1.0)
        self._plat_name = platform_name

    def sample_telemetry(self) -> SystemTelemetry:
        now = time.time()
        return SystemTelemetry(
            cpu_percent=0.0,
            ram_percent=0.0,
            avail_ram_mb=0.0,
            total_ram_mb=0.0,
            timestamp=now,
            is_real=False,
            is_valid=False,
            error_message=f"Hardware telemetry is not implemented for platform '{self._plat_name}'.",
            platform_name=self._plat_name,
        )


def create_telemetry_provider(
    force_platform: Optional[str] = None,
    cache_ttl_sec: float = 0.5,
) -> BaseTelemetryProvider:
    """Factory creating the appropriate telemetry provider for the host environment."""
    plat = (force_platform or platform.system()).lower()
    if plat == "windows":
        return WindowsTelemetryProvider(cache_ttl_sec=cache_ttl_sec)
    elif plat == "linux":
        return LinuxTelemetryProvider(cache_ttl_sec=cache_ttl_sec)
    else:
        return UnsupportedPlatformProvider(platform_name=plat)


# Backward-compatible SystemTelemetryProvider delegation class
class SystemTelemetryProvider(BaseTelemetryProvider):
    """Backward-compatible wrapper delegating to the appropriate platform provider."""

    def __init__(self, cache_ttl_sec: float = 0.5, force_platform: Optional[str] = None):
        super().__init__(cache_ttl_sec=cache_ttl_sec)
        self._delegate = create_telemetry_provider(
            force_platform=force_platform,
            cache_ttl_sec=cache_ttl_sec,
        )

    def sample_telemetry(self) -> SystemTelemetry:
        return self._delegate.sample_telemetry()

    def get_telemetry(self) -> SystemTelemetry:
        return self._delegate.get_telemetry()


# Global singleton provider instance
_PROVIDER: Optional[BaseTelemetryProvider] = None
_INIT_LOCK = threading.Lock()


def get_system_telemetry(force_refresh: bool = False) -> SystemTelemetry:
    """Retrieve current genuine system hardware telemetry from host kernel."""
    global _PROVIDER
    if _PROVIDER is None:
        with _INIT_LOCK:
            if _PROVIDER is None:
                _PROVIDER = create_telemetry_provider()
    return _PROVIDER.get_telemetry()
