import sys
import tempfile
import unittest
from pathlib import Path, PureWindowsPath
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from device import (  # noqa: E402
    BlueStacksEmulatorDevice,
    EmulatorDevice,
    GooglePlayGamesDevEmulatorDevice,
    MuMuEmulatorDevice,
    PhysicalAndroidDevice,
    create_device,
    infer_device_type,
)


class Setting:
    DEVICE_TYPE = "mumu"
    EMU_PATH = ""
    EMU_INDEX = 0
    ADB_ADRESS = "127.0.0.1:16384"
    ADB_PATH = ""
    _ADBDEVICE = None


class Runtime:
    _RUNNING_EMU_PID = None


class DevicePathTests(unittest.TestCase):
    def make_device(self, device_type, emu_path="", adb_path=""):
        setting = Setting()
        setting.DEVICE_TYPE = device_type
        setting.EMU_PATH = emu_path
        setting.ADB_PATH = adb_path
        return create_device(setting, Runtime())

    def test_registry_creates_expected_device_types(self):
        self.assertIsInstance(self.make_device("mumu", r"C:\MuMu\shell"), MuMuEmulatorDevice)
        self.assertIsInstance(self.make_device("bluestacks", r"C:\BlueStacks"), BlueStacksEmulatorDevice)
        self.assertIsInstance(self.make_device("gpg_dev", r"C:\GPG\current\emulator"), GooglePlayGamesDevEmulatorDevice)
        self.assertIsInstance(self.make_device("physical", adb_path=r"C:\adb\adb.exe"), PhysicalAndroidDevice)

    def test_mumu_paths_are_relative_to_install_root(self):
        device = self.make_device("mumu", r"C:\Program Files\Netease\MuMuPlayer")
        root = PureWindowsPath(r"C:\Program Files\Netease\MuMuPlayer")
        shell = root / "nx_device" / "12.0" / "shell"
        self.assertEqual(device.install_root, root)
        self.assertEqual(device.shell_dir, shell)
        self.assertEqual(device.adb_path, shell / "adb.exe")
        self.assertIn(device.emu_path.name, ["MuMuNxDevice.exe", "MuMuPlayer.exe"])
        self.assertEqual(device.emu_path.parent, shell)

    def test_mumu_accepts_legacy_executable_path(self):
        device = self.make_device("mumu", r"C:\Program Files\Netease\MuMuPlayer\nx_device\12.0\shell\MuMuNxDevice.exe")
        root = PureWindowsPath(r"C:\Program Files\Netease\MuMuPlayer")
        self.assertEqual(device.install_root, root)
        self.assertEqual(device.adb_path, root / "nx_device" / "12.0" / "shell" / "adb.exe")

    def test_bluestacks_paths_are_relative_to_install_root(self):
        device = self.make_device("bluestacks", r"C:\Program Files\BlueStacks_nxt")
        root = PureWindowsPath(r"C:\Program Files\BlueStacks_nxt")
        self.assertEqual(device.install_root, root)
        self.assertEqual(device.emu_path, root / "HD-Player.exe")
        self.assertEqual(device.adb_path, root / "HD-Adb.exe")

    def test_bluestacks_accepts_legacy_executable_path(self):
        device = self.make_device("bluestacks", r"C:\BlueStacks\HD-Adb.exe")
        root = PureWindowsPath(r"C:\BlueStacks")
        self.assertEqual(device.install_root, root)
        self.assertEqual(device.emu_path, root / "HD-Player.exe")
        self.assertEqual(device.adb_path, root / "HD-Adb.exe")

    def test_gpg_dev_paths_are_relative_to_emulator_root(self):
        root = PureWindowsPath(r"C:\Program Files\Google\Play Games Developer Emulator")
        emulator = root / "current" / "emulator"
        device = self.make_device("gpg_dev", str(root))
        self.assertEqual(device.install_root, root)
        self.assertEqual(device.base_dir, emulator)
        self.assertEqual(device.adb_path, emulator / "adb.exe")
        self.assertEqual(device.emu_path, root / "current" / "service" / "Service.exe")
        self.assertEqual(device.startup_bin, root / "Bootstrapper.exe")
        self.assertEqual(device.default_adb_address, "localhost:6520")

    def test_gpg_dev_multiple_crosvm_processes_are_single_emulator(self):
        device = self.make_device("gpg_dev", r"C:\GPG")
        with patch.object(device, "detect_running_pids", return_value=[101, 102, 103]):
            device.capture_running_pid()
        self.assertIsNone(device.runtime_context._RUNNING_EMU_PID)
        with patch.object(device, "detect_running_pids", return_value=[101, 102, 103]):
            self.assertTrue(device.is_running())

    def test_gpg_dev_accepts_bundled_binary_path(self):
        device = self.make_device("gpg_dev", r"C:\GPG\current\emulator\adb.exe")
        root = PureWindowsPath(r"C:\GPG")
        emulator = root / "current" / "emulator"
        self.assertEqual(device.install_root, root)
        self.assertEqual(device.base_dir, emulator)
        self.assertEqual(device.adb_path, emulator / "adb.exe")

    def test_physical_uses_explicit_adb_path(self):
        device = self.make_device("physical", adb_path=r"C:\Android\platform-tools\adb.exe")
        self.assertEqual(device.adb_path, PureWindowsPath(r"C:\Android\platform-tools\adb.exe"))

    def test_physical_uses_existing_default_adb_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            adb_path = Path(temp_dir) / "platform-tools" / "adb.exe"
            adb_path.parent.mkdir(parents=True)
            adb_path.touch()
            setting = Setting()
            setting.DEVICE_TYPE = "physical"
            setting.ADB_PATH = ""
            with patch.object(PhysicalAndroidDevice, "default_adb_paths", [str(adb_path)]):
                device = create_device(setting, Runtime())
                self.assertEqual(device.adb_path, adb_path)
                self.assertTrue(device.validate_adb_path())

    def test_infer_device_type_supports_legacy_bluestacks_paths(self):
        setting = Setting()
        setting.DEVICE_TYPE = None
        setting.EMU_PATH = r"C:\BlueStacks\HD-Player.exe"
        self.assertEqual(infer_device_type(setting), "bluestacks")

    def test_infer_device_type_supports_gpg_dev_paths(self):
        for path in [
            r"C:\Program Files\Google\Play Games Developer Emulator",
            r"C:\Program Files\Google\Play Games Developer Emulator\current\emulator",
            r"C:\Program Files\Google\Play Games Developer Emulator\current\emulator\crosvm.exe",
            r"C:\Program Files\Google\Play Games Developer Emulator\current\service\Service.exe",
        ]:
            with self.subTest(path=path):
                setting = Setting()
                setting.DEVICE_TYPE = None
                setting.EMU_PATH = path
                self.assertEqual(infer_device_type(setting), "gpg_dev")

    def test_unknown_device_type_falls_back_to_mumu(self):
        self.assertIsInstance(self.make_device("unknown", r"C:\MuMu\shell"), MuMuEmulatorDevice)

    def test_validate_adb_path_windows_paths_do_not_raise_on_non_windows(self):
        devices = [
            self.make_device("mumu", r"C:\__WVD_MISSING__\MuMuPlayer"),
            self.make_device("bluestacks", r"C:\__WVD_MISSING__\BlueStacks_nxt"),
            self.make_device("gpg_dev", r"C:\__WVD_MISSING__\Play Games Developer Emulator"),
            self.make_device("physical", adb_path=r"C:\Android\platform-tools\adb.exe"),
        ]
        for device in devices:
            with self.subTest(device=device.device_type):
                self.assertFalse(device.validate_adb_path())

    def test_start_emulator_missing_windows_path_returns_false(self):
        devices = [
            self.make_device("mumu", r"C:\__WVD_MISSING__\MuMuPlayer"),
            self.make_device("bluestacks", r"C:\__WVD_MISSING__\BlueStacks_nxt"),
            self.make_device("gpg_dev", r"C:\__WVD_MISSING__\Play Games Developer Emulator"),
        ]
        for device in devices:
            with self.subTest(device=device.device_type):
                self.assertFalse(device.start_emulator())

    def test_default_install_root_can_satisfy_validate_adb_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            shell = root / "nx_device" / "12.0" / "shell"
            shell.mkdir(parents=True)
            (shell / "adb.exe").touch()
            setting = Setting()
            setting.DEVICE_TYPE = "mumu"
            setting.EMU_PATH = ""
            runtime = Runtime()
            with patch.object(MuMuEmulatorDevice, "default_install_roots", [str(root)]):
                device = create_device(setting, runtime)
                self.assertEqual(device.install_root, root)
                self.assertTrue(device.validate_adb_path())

    def test_connect_does_not_kill_emulator_immediately_after_start(self):
        class FakeResult:
            stdout = "List of devices attached\n"
            stderr = ""
            returncode = 0

        class FakeEmulator(EmulatorDevice):
            device_type = "fake"
            process_names = ["fake.exe"]
            default_install_roots = ["/fake"]

            @property
            def adb_path(self):
                return Path("adb")

            def __init__(self, setting, runtime_context):
                super().__init__(setting, runtime_context)
                self.started = 0
                self.killed = 0

            def is_running(self):
                return False

            def start_emulator(self):
                self.started += 1
                return True

            def kill_emulator(self):
                self.killed += 1

            def _run_adb(self, *args, timeout=10):
                return FakeResult()

            def _create_ppadb_device(self):
                return None

        setting = Setting()
        setting.EMU_PATH = "/fake"
        setting.ADB_ADRESS = "127.0.0.1:16384"
        device = FakeEmulator(setting, Runtime())
        with patch("device.time.sleep", return_value=None):
            self.assertIsNone(device.connect())
        self.assertGreater(device.started, 0)
        self.assertEqual(device.killed, 0)

    def test_adb_device_state_requires_exact_device_row(self):
        device = self.make_device("gpg_dev", r"C:\GPG")
        device.setting.ADB_ADRESS = "localhost:6520"
        self.assertEqual(
            device._adb_device_state("List of devices attached\nlocalhost:6520\tdevice\n"),
            "device",
        )
        self.assertEqual(
            device._adb_device_state("List of devices attached\nlocalhost:6520\toffline\n"),
            "offline",
        )
        self.assertIsNone(device._adb_device_state("List of devices attached\nlocalhost:6521\tdevice\n"))

    def test_connect_skips_tcp_connect_when_device_is_already_ready(self):
        class FakeResult:
            stderr = ""
            returncode = 0

            def __init__(self, stdout):
                self.stdout = stdout

        class FakeGpg(GooglePlayGamesDevEmulatorDevice):
            def __init__(self, setting, runtime_context):
                super().__init__(setting, runtime_context)
                self.calls = []

            @property
            def adb_path(self):
                return Path("adb")

            def _run_adb(self, *args, timeout=10):
                self.calls.append(args)
                return FakeResult("List of devices attached\nlocalhost:6520\tdevice\n")

            def _create_ppadb_device(self):
                return object()

            def after_connect(self):
                pass

        setting = Setting()
        setting.DEVICE_TYPE = "gpg_dev"
        setting.ADB_ADRESS = "localhost:6520"
        device = FakeGpg(setting, Runtime())
        self.assertIsNotNone(device.connect())
        self.assertNotIn(("connect", "localhost:6520"), device.calls)

    def test_gpg_connect_failure_does_not_kill_emulator_while_booting(self):
        class FakeResult:
            stdout = "List of devices attached\n"
            stderr = ""
            returncode = 0

        class FakeGpg(GooglePlayGamesDevEmulatorDevice):
            def __init__(self, setting, runtime_context):
                super().__init__(setting, runtime_context)
                self.killed = 0

            @property
            def adb_path(self):
                return Path("adb")

            def _run_adb(self, *args, timeout=10):
                return FakeResult()

            def is_running(self):
                return True

            def kill_emulator(self):
                self.killed += 1

        setting = Setting()
        setting.DEVICE_TYPE = "gpg_dev"
        setting.ADB_ADRESS = "localhost:6520"
        device = FakeGpg(setting, Runtime())
        with patch("device.time.sleep", return_value=None):
            self.assertIsNone(device.connect())
        self.assertEqual(device.killed, 0)

    def test_connect_rejects_devices_output_when_adb_exit_code_fails(self):
        class FakeResult:
            stdout = "List of devices attached\nphysical-serial\tdevice\n"
            stderr = "adb failed"
            returncode = 1

        class FakePhysical(PhysicalAndroidDevice):
            def __init__(self, setting, runtime_context):
                super().__init__(setting, runtime_context)
                self.created_device = False

            @property
            def adb_path(self):
                return Path("adb")

            def _run_adb(self, *args, timeout=10):
                return FakeResult()

            def _create_ppadb_device(self):
                self.created_device = True
                return object()

        setting = Setting()
        setting.DEVICE_TYPE = "physical"
        setting.ADB_ADRESS = "physical-serial"
        setting.ADB_PATH = "adb"
        device = FakePhysical(setting, Runtime())
        with patch("device.time.sleep", return_value=None):
            self.assertIsNone(device.connect())
        self.assertFalse(device.created_device)

    def test_gpg_restart_target_kills_service_then_starts_bootstrapper(self):
        device = self.make_device("gpg_dev", r"C:\Program Files\Google\Play Games Developer Emulator")
        with patch("device.time.sleep", return_value=None), patch.object(device, "kill_emulator") as kill_emulator, patch.object(
            device, "start_emulator", return_value=True
        ) as start_emulator, patch.object(device, "_run_adb") as run_adb:
            self.assertTrue(device.restart_target())

        kill_emulator.assert_called_once_with()
        start_emulator.assert_called_once_with()
        run_adb.assert_not_called()

    def test_gpg_detect_running_pids_filters_service_by_install_root(self):
        device = self.make_device("gpg_dev", r"C:\Program Files\Google\Play Games Developer Emulator")

        class FakeResult:
            stdout = "1234\nnot-a-pid\n"
            stderr = ""

        with patch("device.os.name", "nt"), patch("device.subprocess.run", return_value=FakeResult()) as run:
            self.assertEqual(device.detect_running_pids(), [1234])

        command = run.call_args.args[0]
        self.assertEqual(command[:3], ["powershell", "-NoProfile", "-Command"])
        self.assertIn("Name = 'Service.exe'", command[3])
        self.assertIn("ExecutablePath.StartsWith", command[3])
        self.assertIn("C:\\Program Files\\Google\\Play Games Developer Emulator\\", command[3])

    def test_gpg_kill_emulator_uses_filtered_pids_not_service_name(self):
        device = self.make_device("gpg_dev", r"C:\Program Files\Google\Play Games Developer Emulator")

        class FakeResult:
            stdout = ""
            stderr = ""
            returncode = 0

        with patch.object(device, "detect_running_pids", return_value=[1234, 5678]), patch(
            "device.subprocess.run", return_value=FakeResult()
        ) as run, patch("device.time.sleep", return_value=None):
            device.kill_emulator()

        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(
            commands,
            [
                ["taskkill", "/F", "/PID", "1234"],
                ["taskkill", "/F", "/PID", "5678"],
            ],
        )
        self.assertFalse(any("/IM" in command for command in commands))

    def test_gpg_emulator_path_points_to_service_process(self):
        root = PureWindowsPath(r"C:\Program Files\Google\Play Games Developer Emulator")
        device = self.make_device("gpg_dev", str(root))
        self.assertEqual(device.emu_path, root / "current" / "service" / "Service.exe")

    def test_after_connect_sets_display_for_gpg_and_physical(self):
        for device_type in ["gpg_dev", "physical"]:
            with self.subTest(device_type=device_type):
                calls = []

                class FakeResult:
                    stdout = ""
                    stderr = ""
                    returncode = 0

                device = self.make_device(device_type, r"C:\GPG", r"C:\Android\platform-tools\adb.exe")
                device.setting.ADB_ADRESS = "device-serial"
                with patch.object(device, "_run_adb", side_effect=lambda *args, **kwargs: calls.append(args) or FakeResult()):
                    device.after_connect()
                self.assertEqual(
                    calls,
                    [
                        ("-s", "device-serial", "shell", "wm", "size", "900x1600"),
                        ("-s", "device-serial", "shell", "wm", "density", "240"),
                    ],
                )

    def test_restore_display_resets_physical_device_display(self):
        calls = []

        class FakeResult:
            stdout = ""
            stderr = ""
            returncode = 0

        device = self.make_device("physical", adb_path=r"C:\Android\platform-tools\adb.exe")
        device.setting.ADB_ADRESS = "physical-serial"
        with patch.object(device, "_run_adb", side_effect=lambda *args, **kwargs: calls.append(args) or FakeResult()):
            self.assertTrue(device.restore_display())

        self.assertEqual(
            calls,
            [
                ("-s", "physical-serial", "shell", "wm", "size", "reset"),
                ("-s", "physical-serial", "shell", "wm", "density", "reset"),
            ],
        )

    def test_restore_display_is_noop_for_emulators(self):
        device = self.make_device("gpg_dev", r"C:\GPG")
        with patch.object(device, "_run_adb") as run_adb:
            self.assertTrue(device.restore_display())
        run_adb.assert_not_called()

    def test_cleanup_after_stop_closes_game_then_resets_physical_display(self):
        adb_calls = []
        shell_calls = []

        class FakeResult:
            stdout = ""
            stderr = ""
            returncode = 0

        class FakeAdbDevice:
            serial = "physical-serial"

            def shell(self, cmd, timeout=5):
                shell_calls.append(cmd)
                return ""

        device = self.make_device("physical", adb_path=r"C:\Android\platform-tools\adb.exe")
        device.setting.ADB_ADRESS = "physical-serial"
        device.setting._ADBDEVICE = FakeAdbDevice()
        with patch.object(device, "_run_adb", side_effect=lambda *args, **kwargs: adb_calls.append(args) or FakeResult()):
            self.assertTrue(device.cleanup_after_stop())

        self.assertEqual(shell_calls, ["am force-stop jp.co.drecom.wizardry.daphne"])
        self.assertEqual(
            adb_calls,
            [
                ("-s", "physical-serial", "shell", "wm", "size", "reset"),
                ("-s", "physical-serial", "shell", "wm", "density", "reset"),
            ],
        )

    def test_cleanup_after_stop_resets_display_if_close_game_fails(self):
        adb_calls = []

        class FakeResult:
            stdout = ""
            stderr = ""
            returncode = 0

        class FakeAdbDevice:
            serial = "physical-serial"

            def shell(self, cmd, timeout=5):
                raise RuntimeError("force-stop failed")

        device = self.make_device("physical", adb_path=r"C:\Android\platform-tools\adb.exe")
        device.setting.ADB_ADRESS = "physical-serial"
        device.setting._ADBDEVICE = FakeAdbDevice()
        with patch.object(device, "_run_adb", side_effect=lambda *args, **kwargs: adb_calls.append(args) or FakeResult()):
            self.assertFalse(device.cleanup_after_stop())

        self.assertEqual(
            adb_calls,
            [
                ("-s", "physical-serial", "shell", "wm", "size", "reset"),
                ("-s", "physical-serial", "shell", "wm", "density", "reset"),
            ],
        )

    def test_cleanup_after_stop_is_noop_for_emulators(self):
        device = self.make_device("gpg_dev", r"C:\GPG")
        with patch.object(device, "_run_adb") as run_adb:
            self.assertTrue(device.cleanup_after_stop())
        run_adb.assert_not_called()

    def test_restart_game_requires_connected_device(self):
        device = self.make_device("physical", adb_path=r"C:\Android\platform-tools\adb.exe")
        with self.assertRaises(RuntimeError):
            device.restart_game()

    def test_restart_game_skips_start_when_activity_unresolved(self):
        calls = []

        class FakeAdbDevice:
            serial = "device"

            def shell(self, cmd, timeout=5):
                calls.append(cmd)
                if "resolve-activity" in cmd:
                    return "No activity found"
                return ""

        device = self.make_device("physical", adb_path=r"C:\Android\platform-tools\adb.exe")
        device.setting._ADBDEVICE = FakeAdbDevice()
        with patch.object(device, "clear_logcat", return_value=None):
            self.assertFalse(device.restart_game())
        self.assertNotIn("am force-stop jp.co.drecom.wizardry.daphne", calls)

    def test_restart_game_clears_all_logcat_buffers_before_start(self):
        adb_calls = []
        shell_calls = []

        class FakeResult:
            stdout = ""
            stderr = ""
            returncode = 0

        class FakeAdbDevice:
            serial = "physical-serial"

            def shell(self, cmd, timeout=5):
                shell_calls.append(cmd)
                if "resolve-activity" in cmd:
                    return "jp.co.drecom.wizardry.daphne/.MainActivity"
                return ""

        device = self.make_device("physical", adb_path=r"C:\Android\platform-tools\adb.exe")
        device.setting.ADB_ADRESS = "physical-serial"
        device.setting._ADBDEVICE = FakeAdbDevice()
        with patch.object(device, "_run_adb", side_effect=lambda *args, **kwargs: adb_calls.append(args) or FakeResult()):
            self.assertTrue(device.restart_game())

        self.assertEqual(adb_calls[0], ("-s", "physical-serial", "shell", "logcat", "-b", "all", "-c"))
        self.assertIn("am force-stop jp.co.drecom.wizardry.daphne", shell_calls)

    def test_graphics_api_crash_scan_reads_all_logcat_buffers_in_python(self):
        calls = []

        class FakeResult:
            stderr = ""
            returncode = 0
            stdout = "\n".join(
                [
                    "normal line",
                    "E Unity: Unable to initialize graphics API Vulkan",
                ]
            )

        device = self.make_device("physical", adb_path=r"C:\Android\platform-tools\adb.exe")
        device.setting.ADB_ADRESS = "physical-serial"
        with patch.object(device, "_run_adb", side_effect=lambda *args, **kwargs: calls.append(args) or FakeResult()):
            logs = device.find_graphics_api_crash_log()

        self.assertEqual(calls[0], ("-s", "physical-serial", "shell", "logcat", "-b", "all", "-d"))
        self.assertIn("Unable to initialize graphics API", logs)

if __name__ == "__main__":
    unittest.main()
