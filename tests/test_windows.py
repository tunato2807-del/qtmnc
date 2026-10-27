"""Windows-target regression tests; do not claim a real Windows machine was tested."""
import base64
import json
from unittest.mock import Mock

import monitor_ssh as m
import test_monitor as helpers
import unittest


class WindowsTests(unittest.TestCase):
    def test_os_is_explicit_and_windows_adapter_can_have_spaces(self):
        env = helpers.ConfigTests().env(MONITOR_OS="windows", MONITOR_IFACE="VMware Network Adapter VMnet8")
        c = m.Config.from_env(env)
        self.assertEqual(c.target_os, "windows")
        self.assertEqual(c.iface, "VMware Network Adapter VMnet8")
        for extra in ({"MONITOR_OS": "invalid"}, {"MONITOR_OS": "windows", "MONITOR_IFACE": "bad\nname"}):
            with self.assertRaises(m.ConfigError):
                m.Config.from_env(helpers.ConfigTests().env(**extra))

    def test_powershell_is_encoded_and_adapter_name_is_a_literal(self):
        c = helpers.config(target_os="windows", iface="Dell's Adapter; $(Get-Process)")
        command = m.windows_command(c)
        script = base64.b64decode(command.split()[-1]).decode("utf-16-le")
        self.assertIn("'Dell''s Adapter; $(Get-Process)'", script)
        self.assertIn("Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor", script)
        self.assertIn("$_.Parent -in $hw", script)
        self.assertNotIn("/proc/", script)
        self.assertLess(len(command), 8191)

    def test_disabled_sensor_is_not_queried(self):
        c = helpers.config(target_os="windows", temp_enabled=False)
        script = base64.b64decode(m.windows_command(c).split()[-1]).decode("utf-16-le")
        self.assertIn("if ($false)", script)

    def test_realistic_json_with_bom_and_missing_sensor(self):
        raw = "\ufeff" + json.dumps({"values": {"cpu": 17, "ram": 62.5, "iface": "up"}, "errors": {"temp": "sensor missing"}})
        sample = m.windows_sample(raw, True)
        self.assertEqual(sample.values["cpu"], 17)
        self.assertEqual(sample.values["ram"], 62.5)
        self.assertIsNone(sample.values["temp"])
        self.assertEqual(set(sample.errors), {"temp"})

    def test_nan_invalid_interface_and_missing_ram_are_unknown(self):
        raw = json.dumps({"values": {"cpu": "NaN", "iface": []}})
        sample = m.windows_sample(raw, False)
        self.assertEqual(set(sample.errors), {"cpu", "ram", "iface"})
        self.assertTrue(all(v is None for v in sample.values.values()))

    def test_non_json_is_not_silently_zero(self):
        for raw in ("", "Access denied", "[]", '{"values": []}'):
            with self.assertRaises(m.DataError):
                m.windows_sample(raw, True)

    def test_windows_probes_use_same_ssh_cleanup_and_error_classification(self):
        obj, client = helpers.SSHTests().collector()
        obj.c.target_os = "windows"
        stdout, stderr = Mock(), Mock()
        stdout.read.return_value = json.dumps({"values": {"cpu": 88, "ram": 64, "iface": "down", "temp": 72}}).encode()
        stderr.read.return_value = b""
        stdout.channel.recv_exit_status.return_value = 0
        client.exec_command.side_effect = None
        client.exec_command.return_value = None, stdout, stderr
        sample = obj.collect()
        self.assertEqual(sample.values["cpu"], 88)
        self.assertEqual(sample.values["iface"], "down")
        self.assertFalse(sample.errors)
        self.assertTrue(client.exec_command.call_args.args[0].startswith("powershell.exe "))
        client.close.assert_not_called()
        obj.close()
        client.close.assert_called_once()

    def test_missing_powershell_still_means_connected_with_unknown_metrics(self):
        obj, client = helpers.SSHTests().collector()
        obj.c.target_os = "windows"
        stdout, stderr = Mock(), Mock()
        stdout.read.return_value = b""
        stderr.read.return_value = b"powershell.exe not found"
        stdout.channel.recv_exit_status.return_value = 1
        client.exec_command.side_effect = None
        client.exec_command.return_value = None, stdout, stderr
        sample = obj.collect()
        self.assertEqual(set(sample.errors), {"cpu", "ram", "iface", "temp"})
        obj.close()
        client.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
