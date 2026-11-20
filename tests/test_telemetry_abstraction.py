"""
test_telemetry_abstraction.py: Unit tests for platform-independent hardware telemetry abstraction.

Tests:
1. WindowsTelemetryProvider returns valid host telemetry when running on Windows.
2. LinuxTelemetryProvider correctly parses mock /proc/meminfo and /proc/stat.
3. UnsupportedPlatformProvider returns explicit is_real=False and is_valid=False without fabricated values.
4. SystemTelemetry.is_stale() accurately identifies fresh vs stale samples.
5. Thread-safety: concurrent telemetry requests execute without race conditions.
"""

import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from setu_netra.routing.system_telemetry import (
    LinuxTelemetryProvider,
    SystemTelemetry,
    UnsupportedPlatformProvider,
    WindowsTelemetryProvider,
    create_telemetry_provider,
    get_system_telemetry,
)


class TestTelemetryAbstraction(unittest.TestCase):
    def test_01_windows_provider_or_host(self):
        tel = get_system_telemetry()
        self.assertIsInstance(tel, SystemTelemetry)
        self.assertGreaterEqual(tel.cpu_percent, 0.0)
        self.assertLessEqual(tel.cpu_percent, 100.0)
        self.assertGreaterEqual(tel.ram_percent, 0.0)
        self.assertLessEqual(tel.ram_percent, 100.0)
        self.assertTrue(tel.is_valid)
        self.assertTrue(tel.is_real)
        self.assertFalse(tel.is_stale(max_age_sec=10.0))

    def test_02_linux_provider_mock_proc_parsing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            meminfo_path = Path(tmpdir) / "meminfo"
            stat_path = Path(tmpdir) / "stat"

            # 16 GB Total, 4 GB Available -> 75% RAM load
            meminfo_content = (
                "MemTotal:       16384000 kB\n"
                "MemFree:         2048000 kB\n"
                "MemAvailable:    4096000 kB\n"
                "Buffers:          512000 kB\n"
                "Cached:          1536000 kB\n"
            )
            with open(meminfo_path, "w", encoding="utf-8") as f:
                f.write(meminfo_content)

            # cpu user nice system idle iowait irq softirq steal
            # total = 100 + 20 + 80 + 800 = 1000, idle = 800 -> 20% CPU
            stat_content = "cpu  100 20 80 800 0 0 0 0\n"
            with open(stat_path, "w", encoding="utf-8") as f:
                f.write(stat_content)

            provider = LinuxTelemetryProvider(
                cache_ttl_sec=0.01,
                proc_meminfo_path=str(meminfo_path),
                proc_stat_path=str(stat_path),
            )

            # Advance stat time
            time.sleep(0.05)
            # Second sample with 50% CPU
            # delta_total = 200, delta_idle = 100 -> ratio = 1 - (100/200) = 50%
            with open(stat_path, "w", encoding="utf-8") as f:
                f.write("cpu  150 30 120 900 0 0 0 0\n")

            sample = provider.sample_telemetry()
            self.assertTrue(sample.is_real)
            self.assertTrue(sample.is_valid)
            self.assertEqual(sample.platform_name, "Linux")
            self.assertAlmostEqual(sample.total_ram_mb, 16000.0, delta=1.0)
            self.assertAlmostEqual(sample.avail_ram_mb, 4000.0, delta=1.0)
            self.assertAlmostEqual(sample.ram_percent, 75.0, delta=1.0)
            self.assertAlmostEqual(sample.cpu_percent, 50.0, delta=5.0)

    def test_03_unsupported_platform_no_fabrication(self):
        provider = UnsupportedPlatformProvider(platform_name="Solaris")
        sample = provider.get_telemetry()
        self.assertFalse(sample.is_real)
        self.assertFalse(sample.is_valid)
        self.assertEqual(sample.cpu_percent, 0.0)
        self.assertEqual(sample.ram_percent, 0.0)
        self.assertIn("not implemented", sample.error_message)

    def test_04_staleness_detection(self):
        old_sample = SystemTelemetry(
            cpu_percent=12.0,
            ram_percent=60.0,
            avail_ram_mb=4000.0,
            total_ram_mb=16000.0,
            timestamp=time.time() - 8.0,
        )
        self.assertTrue(old_sample.is_stale(max_age_sec=5.0))
        self.assertFalse(old_sample.is_stale(max_age_sec=15.0))

    def test_05_concurrent_telemetry_access(self):
        provider = create_telemetry_provider()
        samples = []

        def worker():
            for _ in range(20):
                s = provider.get_telemetry()
                samples.append(s)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(samples), 100)
        self.assertTrue(all(s.is_valid for s in samples))


if __name__ == "__main__":
    unittest.main()
