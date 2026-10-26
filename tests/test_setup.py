"""Setup regression tests: configuration integrity and real loopback host-key checks."""
import base64
from contextlib import redirect_stdout
import hashlib
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from dotenv import dotenv_values

import monitor_ssh as m
import device_monitor.config as config_module
import setup_project as s
import test_integration as fixtures


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="monitor setup ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.file = self.root / ".env"

    def settings(self):
        return {"MONITOR_HOST": "192.168.73.129", "MONITOR_OS": "linux", "MONITOR_PROTOCOL": "ssh",
                "SSH_USER": "tuanto", "SSH_PASSWORD": "local-fixture-password", "MONITOR_IFACE": "ens33",
                "MONITOR_TEMP_ENABLED": "false", "TELEGRAM_TOKEN": "123:fake_local_bot", "TELEGRAM_CHAT_ID": "1000"}

    def test_secrets_roundtrip_without_expanding_shell_or_environment_variables(self):
        values = self.settings()
        values["SSH_PASSWORD"] = r"it's\a $HOME " + "$" + r"{HOME} $(echo example) #literal"
        s.save_settings(self.file, values)
        self.assertEqual(dotenv_values(self.file, interpolate=False)["SSH_PASSWORD"], values["SSH_PASSWORD"])
        with patch.dict(os.environ, {"SSH_PASSWORD": "old"}, clear=True):
            m.load_environment_file(self.file)
            self.assertEqual(os.environ["SSH_PASSWORD"], values["SSH_PASSWORD"])

    def test_preserves_comments_unknown_settings_and_unchanged_secrets(self):
        self.file.write_text("# my settings\nCUSTOM_SETTING='keep me'\nSSH_PASSWORD='keep-secret'\n")
        s.save_settings(self.file, {"MONITOR_HOST": "192.168.73.129"})
        read = dotenv_values(self.file, interpolate=False)
        self.assertEqual(read["CUSTOM_SETTING"], "keep me")
        self.assertEqual(read["SSH_PASSWORD"], "keep-secret")
        self.assertIn("# my settings", self.file.read_text())

    def test_atomic_write_failure_preserves_original_and_removes_temporary_secret_file(self):
        self.file.write_text("CUSTOM_SETTING='old'\n")
        original = self.file.read_bytes()
        with patch("dotenv.set_key", side_effect=OSError("simulated disk error")):
            with self.assertRaises(OSError):
                s.save_settings(self.file, self.settings())
        self.assertEqual(self.file.read_bytes(), original)
        self.assertEqual(list(self.root.glob(".env.*.tmp")), [])

    def test_symlink_profile_not_replaced(self):
        target = self.root / "real.env"
        target.write_text("MY_VALUE='keep'\n")
        self.file.symlink_to(target)
        with self.assertRaises(ValueError):
            s.save_settings(self.file, self.settings())
        self.assertEqual(target.read_text(), "MY_VALUE='keep'\n")

    def test_new_wizard_uses_requested_linux_defaults_and_saves_valid_profile(self):
        def ask(label, default=""):
            return "1000" if label == "Telegram chat ID" else default
        def secret(label, previous=""):
            return "123:fake_local_bot" if label.startswith("Token") else "local-fixture-password"
        output = io.StringIO()
        with patch.object(s, "ask", side_effect=ask), patch.object(s, "ask_secret", side_effect=secret), redirect_stdout(output):
            s.configure(self.file)
        c = m.Config.from_env(dotenv_values(self.file, interpolate=False))
        self.assertEqual((c.host, c.ssh_user, c.iface, c.target_os), ("192.168.73.129", "tuanto", "ens33", "linux"))
        self.assertFalse(c.temp_enabled)
        self.assertNotIn("fake_local_bot", output.getvalue())
        self.assertNotIn("local-fixture-password", output.getvalue())

    def test_wizard_enter_preserves_saved_credentials(self):
        s.save_settings(self.file, self.settings())
        with patch.object(s, "ask", side_effect=lambda label, default="": default), patch.object(s, "ask_secret", side_effect=lambda label, previous="": previous), redirect_stdout(io.StringIO()):
            s.configure(self.file)
        read = dotenv_values(self.file, interpolate=False)
        self.assertEqual(read["SSH_PASSWORD"], self.settings()["SSH_PASSWORD"])
        self.assertEqual(read["TELEGRAM_TOKEN"], self.settings()["TELEGRAM_TOKEN"])

    def test_invalid_wizard_values_do_not_overwrite_existing_config(self):
        s.save_settings(self.file, self.settings())
        original = self.file.read_bytes()
        def ask(label, default=""):
            return "bad;host" if label == "IP/hostname máy đích" else default
        with patch.object(s, "ask", side_effect=ask), patch.object(s, "ask_secret", side_effect=lambda label, previous="": previous), redirect_stdout(io.StringIO()):
            with self.assertRaises(s.SetupError):
                s.configure(self.file)
        self.assertEqual(self.file.read_bytes(), original)

    def test_explicit_profile_wins_over_stale_terminal_settings(self):
        s.save_settings(self.file, self.settings())
        with patch.dict(os.environ, {"MONITOR_OS": "windows", "MONITOR_HOST": "192.168.73.1"}, clear=True):
            m.load_environment_file(self.file)
            self.assertEqual(m.Config.from_env().target_os, "linux")
            self.assertEqual(m.Config.from_env().host, "192.168.73.129")

    def test_default_profile_preserves_intentional_command_level_overrides(self):
        s.save_settings(self.file, self.settings())
        with patch.object(config_module, "ROOT", self.root), patch.dict(os.environ, {"RAM_THRESHOLD": "0", "RECOVERY_MARGIN": "0"}, clear=True):
            m.load_environment_file()
            self.assertEqual(m.Config.from_env().thresholds["ram"], 0)

    def test_missing_explicit_profile_is_an_error(self):
        with self.assertRaises(m.ConfigError):
            m.load_environment_file(self.file)

    def test_auth_choice_reprompts_without_echoing_accidentally_typed_password(self):
        with patch("builtins.input",side_effect=["accidental-secret","password"]), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(s.choose("Xác thực",("password","key","agent"),"password"),"password")
        self.assertNotIn("accidental-secret",out.getvalue())

    def test_gns3_wizard_creates_separate_profile_and_keeps_gns3_defaults(self):
        def ask(label,default=""):
            return "1000" if label=="Telegram chat ID" else default
        def secret(label,previous=""):
            return "123:fake_local_bot" if label.startswith("Token") else "local-fixture-password"
        with patch.object(s,"ask",side_effect=ask), patch.object(s,"ask_secret",side_effect=secret), redirect_stdout(io.StringIO()):
            s.configure(self.file,s.ROOT/"examples/gns3.env")
        c=m.Config.from_env(dotenv_values(self.file,interpolate=False))
        self.assertEqual((c.host,c.iface,c.interval),("192.168.10.129","gns3test",5))
        self.assertEqual(c.snmp_profile,"linux-extend")

    def test_reads_utf8_bom_profiles(self):
        self.file.write_text("MONITOR_HOST='192.168.73.129'\n", encoding="utf-8-sig")
        with patch.dict(os.environ, {}, clear=True):
            m.load_environment_file(self.file)
            self.assertEqual(os.environ["MONITOR_HOST"], "192.168.73.129")

    def test_existing_venv_reused_and_install_failures_not_ignored(self):
        python = self.root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        python.parent.mkdir(parents=True)
        python.touch()
        with patch.object(s.venv, "EnvBuilder") as builder, patch.object(s.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "pip")) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                s.install_dependencies(self.root)
            builder.assert_not_called()
            self.assertTrue(run.call_args.kwargs["check"])
            self.assertNotIn("--trusted-host", run.call_args.args[0])
            self.assertFalse(run.call_args.kwargs.get("shell", False))

    def test_invalid_existing_venv_not_deleted(self):
        directory = self.root / ".venv"
        directory.mkdir()
        (directory / "user.txt").write_text("keep")
        with self.assertRaises(ValueError):
            s.install_dependencies(self.root)
        self.assertEqual((directory / "user.txt").read_text(), "keep")

    def test_setup_skip_check_preserves_existing_file_and_makes_no_ssh_connection(self):
        s.save_settings(self.file, self.settings())
        before = self.file.read_bytes()
        with patch.dict(os.environ, {}, clear=True), patch.object(s, "configure") as configure, patch.object(s, "verify_ssh") as verify, redirect_stdout(io.StringIO()) as output:
            result = s.main(["--finish", "--skip-ssh-check", "--env-file", str(self.file)])
        self.assertEqual(result, 0)
        configure.assert_not_called()
        verify.assert_not_called()
        self.assertEqual(self.file.read_bytes(), before)
        self.assertIn("Chưa kiểm tra kết nối", output.getvalue())


@unittest.skipIf(fixtures.paramiko is None, "Install requirements.txt")
@unittest.skipUnless(__import__("sys").platform.startswith("linux"), "Uses the local Linux SSH fixture")
class SetupSSHTests(unittest.TestCase):
    def config(self, port, known):
        return m.Config(host="127.0.0.1", ssh_port=port, ssh_user="fixture",
                        ssh_password="local-fixture-only", known_hosts=str(known), timeout=3)

    def test_independently_matching_fingerprint_required_and_persisted(self):
        with tempfile.TemporaryDirectory() as directory, fixtures.ssh_device() as (port, key):
            known = Path(directory) / "known_hosts"
            fingerprint = "SHA256:" + base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip("=")
            with patch("builtins.input", return_value=fingerprint), redirect_stdout(io.StringIO()):
                s.verify_ssh(self.config(port, known))
            keys = fixtures.paramiko.HostKeys(str(known))
            self.assertEqual(keys[f"[127.0.0.1]:{port}"][key.get_name()], key)

    def test_wrong_fingerprint_never_saved(self):
        with tempfile.TemporaryDirectory() as directory, fixtures.ssh_device() as (port, key):
            known = Path(directory) / "known_hosts"
            with patch("builtins.input", return_value="SHA256:incorrect"), redirect_stdout(io.StringIO()):
                with self.assertRaises(fixtures.paramiko.SSHException):
                    s.verify_ssh(self.config(port, known))
            self.assertFalse(known.exists())

    def test_full_ssh_keygen_line_is_accepted_without_trusting_a_different_key(self):
        with tempfile.TemporaryDirectory() as directory, fixtures.ssh_device() as (port,key):
            known=Path(directory)/"known_hosts"
            fingerprint="SHA256:"+base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip("=")
            with patch("builtins.input",return_value=f"2048 {fingerprint} root@fixture (RSA)"), redirect_stdout(io.StringIO()):
                s.verify_ssh(self.config(port,known))
            self.assertTrue(known.is_file())

    def test_existing_matching_key_reused_without_prompt(self):
        with tempfile.TemporaryDirectory() as directory, fixtures.ssh_device() as (port, key):
            known = Path(directory) / "known_hosts"
            before = f"# existing user comment\n[127.0.0.1]:{port} {key.get_name()} {key.get_base64()}\n"
            known.write_text(before)
            with patch("builtins.input") as ask, redirect_stdout(io.StringIO()):
                s.verify_ssh(self.config(port, known))
            ask.assert_not_called()
            self.assertEqual(known.read_text(), before)

    def test_changed_key_rejected_without_overwriting_existing_file(self):
        with tempfile.TemporaryDirectory() as directory, fixtures.ssh_device() as (port, key):
            known = Path(directory) / "known_hosts"
            other = fixtures.paramiko.RSAKey.generate(2048)
            before = f"[127.0.0.1]:{port} {other.get_name()} {other.get_base64()}\n"
            known.write_text(before)
            with patch("builtins.input") as ask:
                with self.assertRaises(fixtures.paramiko.BadHostKeyException):
                    s.verify_ssh(self.config(port, known))
            ask.assert_not_called()
            self.assertEqual(known.read_text(), before)


if __name__ == "__main__":
    unittest.main()
