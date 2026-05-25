import os
import subprocess
import sys
import time
import unittest
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from device import create_device  # noqa: E402


class DummySetting:
    DEVICE_TYPE = os.environ.get("WVD_TEST_DEVICE_TYPE", "mumu")
    EMU_PATH = os.environ.get("WVD_TEST_EMU_PATH")
    EMU_INDEX = int(os.environ.get("WVD_TEST_EMU_INDEX", "0"))
    ADB_ADRESS = os.environ.get("WVD_TEST_ADB_ADDRESS", "127.0.0.1:16384")
    ADB_PATH = os.environ.get("WVD_TEST_ADB_PATH", "")
    _ADBDEVICE = None


class DummyRuntime:
    _RUNNING_EMU_PID = None


def adb_path_for(setting):
    if setting.ADB_PATH:
        return Path(setting.ADB_PATH)
    if setting.DEVICE_TYPE == "mumu" and setting.EMU_PATH:
        path = Path(setting.EMU_PATH)
        if path.name.lower() in ["adb.exe", "mumuplayer.exe", "mumunxdevice.exe"]:
            path = path.parent
        if path.name.lower() == "shell":
            return path / "adb.exe"
        return path / "nx_device" / "12.0" / "shell" / "adb.exe"
    if setting.DEVICE_TYPE == "bluestacks" and setting.EMU_PATH:
        path = Path(setting.EMU_PATH)
        if path.name.lower() in ["hd-adb.exe", "hd-player.exe"]:
            path = path.parent
        return path / "HD-Adb.exe"
    if setting.DEVICE_TYPE == "gpg_dev" and setting.EMU_PATH:
        path = Path(setting.EMU_PATH)
        if path.name.lower() in ["adb.exe", "crosvm.exe", "service.exe"]:
            path = path.parent
        if path.name.lower() == "service":
            path = path.parent.parent / "emulator"
        if path.name.lower() == "emulator":
            return path / "adb.exe"
        return path / "current" / "emulator" / "adb.exe"
    return None


RUN_DEVICE_TESTS = (
    os.environ.get("WVD_RUN_DEVICE_TESTS") == "1"
    or os.environ.get("WVD_RUN_EMULATOR_TESTS") == "1"
)
RUN_EMULATOR_RESTART_TESTS = os.environ.get("WVD_RUN_EMULATOR_RESTART_TESTS") == "1"


@unittest.skipUnless(
    RUN_DEVICE_TESTS,
    "set WVD_RUN_DEVICE_TESTS=1 to run real device integration tests",
)
class RealDeviceIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.setting = DummySetting()
        cls.runtime = DummyRuntime()
        cls.adb_path = adb_path_for(cls.setting)
        if cls.adb_path is None:
            raise unittest.SkipTest("WVD_TEST_ADB_PATH or WVD_TEST_EMU_PATH is required")
        if not cls.adb_path.exists():
            raise unittest.SkipTest(f"ADB executable does not exist: {cls.adb_path}")
        cls.device = create_device(cls.setting, cls.runtime)
        cls.package_name = os.environ.get("WVD_TEST_PACKAGE", "jp.co.drecom.wizardry.daphne")

    def raw_adb(self, *args, timeout=10):
        return subprocess.run(
            [str(self.adb_path), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def assert_target_in_adb_devices(self):
        result = self.raw_adb("devices")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(self.setting.ADB_ADRESS, result.stdout)
        self.assertIn("device", result.stdout)

    def test_adb_devices_contains_target(self):
        if ":" in self.setting.ADB_ADRESS:
            self.raw_adb("connect", self.setting.ADB_ADRESS)
        self.assert_target_in_adb_devices()

    def test_device_connect_and_shell(self):
        adb_device = self.device.connect()
        self.assertIsNotNone(adb_device)
        self.assertEqual(adb_device.serial, self.setting.ADB_ADRESS)
        self.assertTrue(self.device.shell("echo WVD_TEST").strip().endswith("WVD_TEST"))

    def test_screencap_returns_parseable_header(self):
        self.device.connect()
        width, height, fmt = self.assert_screencap_parseable()
        self.assertGreater(width, 0)
        self.assertGreater(height, 0)
        self.assertIn(fmt, [1, 2, 3, 4])

    def assert_screencap_parseable(self):
        result = self.device.screencap()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertGreaterEqual(len(result.stdout), 12)
        width = int.from_bytes(result.stdout[0:4], "little")
        height = int.from_bytes(result.stdout[4:8], "little")
        fmt = int.from_bytes(result.stdout[8:12], "little")
        return width, height, fmt

    def save_png_screenshot(self, name_prefix="integration_screenshot"):
        artifact_dir = ROOT / "logs" / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = artifact_dir / f"{name_prefix}_{timestamp}.png"

        result = subprocess.run(
            [str(self.adb_path), "-s", self.setting.ADB_ADRESS, "exec-out", "screencap", "-p"],
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith(b"\x89PNG\r\n\x1a\n"))
        output_path.write_bytes(result.stdout)
        self.assertGreater(output_path.stat().st_size, 1024)
        return output_path

    def wait_for_package_pid(self, timeout=30):
        deadline = time.time() + timeout
        while time.time() < deadline:
            pid_output = self.device.shell(f"pidof {self.package_name}").strip()
            if pid_output:
                self.assertTrue(pid_output.split()[0].isdigit())
                return pid_output
            time.sleep(1)
        self.fail(f"package did not start within {timeout}s: {self.package_name}")

    def test_game_package_resolves_when_installed(self):
        self.device.connect()
        result = self.device.shell(f"cmd package resolve-activity --brief {self.package_name}").strip()
        self.assertNotIn("No activity found", result)
        self.assertIn("/", result)

    def test_restart_game_on_real_device(self):
        self.device.connect()
        self.assertTrue(self.device.restart_game(self.package_name))
        self.wait_for_package_pid()

    def test_force_restart_adb_reconnects_real_device(self):
        adb_device = self.device.connect(force_restart_adb=True)
        self.assertIsNotNone(adb_device)
        self.assertEqual(adb_device.serial, self.setting.ADB_ADRESS)
        self.assert_target_in_adb_devices()

    @unittest.skipUnless(
        RUN_EMULATOR_RESTART_TESTS,
        "set WVD_RUN_EMULATOR_RESTART_TESTS=1 to kill and restart the emulator process",
    )
    def test_force_restart_emulator_reconnects_real_device(self):
        if self.setting.DEVICE_TYPE == "physical":
            self.skipTest("physical device cannot restart emulator process")

        adb_device = self.device.connect(force_restart_emu=True)
        self.assertIsNotNone(adb_device)
        self.assertEqual(adb_device.serial, self.setting.ADB_ADRESS)
        self.assert_target_in_adb_devices()

    @unittest.skipUnless(
        RUN_EMULATOR_RESTART_TESTS,
        "set WVD_RUN_EMULATOR_RESTART_TESTS=1 to kill and restart the emulator process",
    )
    def test_restart_emulator_start_game_and_screenshot(self):
        if self.setting.DEVICE_TYPE == "physical":
            self.skipTest("physical device cannot restart emulator process")

        adb_device = self.device.connect(force_restart_emu=True)
        self.assertIsNotNone(adb_device)
        self.assertEqual(adb_device.serial, self.setting.ADB_ADRESS)

        self.assertTrue(self.device.restart_game(self.package_name))
        self.wait_for_package_pid()
        time.sleep(10)

        width, height, fmt = self.assert_screencap_parseable()
        self.assertGreaterEqual(width, 100)
        self.assertGreaterEqual(height, 100)
        self.assertIn(fmt, [1, 2, 3, 4])
        screenshot_path = self.save_png_screenshot("restart_emulator_start_game")
        print(f"saved screenshot: {screenshot_path}")


if __name__ == "__main__":
    unittest.main()
