"""Bootstrap contracts and recovery without downloading dependencies."""

import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import bootstrap


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="starter tests with spaces ")
        self.addCleanup(self.temporary.cleanup)
        self.layout = bootstrap.Layout(Path(self.temporary.name))
        self.tools = bootstrap.Prerequisites("/tools with spaces/npm", "pip", None)

    def write(self, name, text=""):
        path = self.layout.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def fake_environment(self):
        self.layout.python.parent.mkdir(parents=True, exist_ok=True)
        self.layout.python.touch()
        return json.dumps({"version": [3, 13], "prefix": str(self.layout.environment),
                           "base_prefix": "/system/python"})

    def template(self):
        self.write(".env.example", "# Example\nDJANGO_SECRET_KEY=\nDJANGO_DEBUG=false\n"
                                  "DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1\n")

    def inputs(self):
        self.template()
        for name in ("manage.py", "requirements.txt", "requirements-dev.txt",
                     "theme/static_src/package.json", "theme/static_src/package-lock.json"):
            self.write(name)

    def test_default_command_and_installer_overrides(self):
        self.assertEqual(bootstrap.parser().parse_args([]).command, "setup")
        self.assertEqual(bootstrap.parser().parse_args(["--installer", "pip"]).installer, "pip")
        self.assertEqual(bootstrap.parser().parse_args(["dev", "--port", "8010"]).port, 8010)

    def test_supported_prerequisites_prefer_uv(self):
        with patch.object(bootstrap.sys, "version_info", (3, 13, 0)), \
             patch.object(bootstrap.shutil, "which", side_effect=lambda name: "/bin/" + name), \
             patch.object(bootstrap, "run", side_effect=["v22.10.0", "10.9.1"]):
            result = bootstrap.prerequisites(layout=self.layout)
        self.assertEqual(result.installer, "uv")

    def test_missing_uv_automatically_uses_pip(self):
        with patch.object(bootstrap.sys, "version_info", (3, 14, 0)), \
             patch.object(bootstrap.shutil, "which", side_effect=lambda name: None if name == "uv" else name), \
             patch.object(bootstrap, "run", side_effect=["v24.0.0", "11.0.0"]):
            self.assertEqual(bootstrap.prerequisites(layout=self.layout).installer, "pip")

    def test_explicit_uv_missing_is_actionable(self):
        with patch.object(bootstrap.sys, "version_info", (3, 13, 0)), \
             patch.object(bootstrap.shutil, "which", side_effect=lambda name: None if name == "uv" else name), \
             patch.object(bootstrap, "run", side_effect=["v24.0.0", "11.0.0"]), \
             self.assertRaisesRegex(bootstrap.BootstrapError, "--installer pip"):
            bootstrap.prerequisites("uv", layout=self.layout)

    def test_unsupported_python_before_any_tool_or_mutation(self):
        with patch.object(bootstrap.sys, "version_info", (3, 11, 0)), \
             patch.object(bootstrap, "run") as run, \
             self.assertRaisesRegex(bootstrap.BootstrapError, "Python 3.12"):
            bootstrap.prerequisites(layout=self.layout)
        run.assert_not_called()
        self.assertEqual(list(self.layout.root.iterdir()), [])

    def test_missing_node_before_any_mutation(self):
        with patch.object(bootstrap.sys, "version_info", (3, 13, 0)), \
             patch.object(bootstrap.shutil, "which", return_value=None), \
             self.assertRaisesRegex(bootstrap.BootstrapError, "Node.js is missing"):
            bootstrap.prerequisites(layout=self.layout)
        self.assertEqual(list(self.layout.root.iterdir()), [])

    def test_unsupported_node_and_npm(self):
        for versions in (["v20.19.0"], ["v22.9.0"], ["v23.0.0"],
                         ["v24.0.0", "9.0.0"], ["v24.0.0", "12.0.0"]):
            with self.subTest(versions=versions), \
                 patch.object(bootstrap.sys, "version_info", (3, 13, 0)), \
                 patch.object(bootstrap.shutil, "which", side_effect=lambda name: name), \
                 patch.object(bootstrap, "run", side_effect=versions), \
                 self.assertRaisesRegex(bootstrap.BootstrapError, "unsupported"):
                bootstrap.prerequisites(layout=self.layout)

    def test_npm_configuration_handles_spaces_and_windows_backslashes(self):
        self.write(".env", "NPM_BIN_PATH='C:\\Program Files\\nodejs\\npm.cmd' # comment\n")
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(bootstrap.npm_override(self.layout), r"C:\Program Files\nodejs\npm.cmd")
        with patch.dict(os.environ, {"NPM_BIN_PATH": "/explicit path/npm"}):
            self.assertEqual(bootstrap.npm_override(self.layout), "/explicit path/npm")

    def test_last_npm_assignment_wins_and_double_quote_escapes_match_dotenv(self):
        self.write(".env", 'NPM_BIN_PATH=/old/npm\nNPM_BIN_PATH="C:\\\\nodejs\\\\npm.cmd"\n')
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(bootstrap.npm_override(self.layout), r"C:\nodejs\npm.cmd")

    def test_blank_and_interpolated_npm_settings_are_actionable(self):
        for value in ("", '""', "${HOME}/bin/npm"):
            self.write(".env", "NPM_BIN_PATH=" + value + "\n")
            with self.subTest(value=value), patch.dict(os.environ, {}, clear=True), \
                 self.assertRaises(bootstrap.BootstrapError):
                bootstrap.npm_override(self.layout)
        with patch.dict(os.environ, {"NPM_BIN_PATH": ""}), \
             self.assertRaisesRegex(bootstrap.BootstrapError, "must not be blank"):
            bootstrap.npm_override(self.layout)

    def test_relative_npm_path_resolves_from_project(self):
        self.write(".env", 'NPM_BIN_PATH="tools with spaces/npm"\n')
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(bootstrap.sys, "version_info", (3, 13, 0)), \
             patch.object(bootstrap.shutil, "which", side_effect=lambda name: name) as which, \
             patch.object(bootstrap, "run", side_effect=["v24.0.0", "11.0.0"]):
            bootstrap.prerequisites(layout=self.layout)
        which.assert_any_call(str(self.layout.root / "tools with spaces/npm"))

    def test_dot_relative_npm_resolves_from_project_when_called_elsewhere(self):
        caller = self.layout.root / "unrelated cwd"
        caller.mkdir()
        for override in ("./npm", "./npm with spaces", "./tools with spaces/npm"):
            self.write(".env", f'NPM_BIN_PATH="{override}"\n')
            with self.subTest(override=override), contextlib.chdir(caller), \
                 patch.dict(os.environ, {}, clear=True), \
                 patch.object(bootstrap.sys, "version_info", (3, 13, 0)), \
                 patch.object(bootstrap.shutil, "which", side_effect=lambda name: name), \
                 patch.object(bootstrap, "run", side_effect=["v24.0.0", "11.0.0"]):
                result = bootstrap.prerequisites(layout=self.layout)
            self.assertEqual(result.npm, str(self.layout.root / override))

    def test_home_relative_npm_preserves_expansion_and_spaces(self):
        override = "~/tools with spaces/npm"
        self.write(".env", f'NPM_BIN_PATH="{override}"\n')
        with patch.dict(os.environ, {"NPM_BIN_PATH": override}), \
             patch.object(bootstrap.sys, "version_info", (3, 13, 0)), \
             patch.object(bootstrap.shutil, "which", side_effect=lambda name: name), \
             patch.object(bootstrap, "run", side_effect=["v24.0.0", "11.0.0"]):
            result = bootstrap.prerequisites(layout=self.layout)
            self.assertEqual(result.npm, str(Path(override).expanduser()))

    def test_missing_inputs_do_not_create_environment(self):
        with self.assertRaisesRegex(bootstrap.BootstrapError, "Required project file"):
            bootstrap.setup(self.layout, self.tools)
        self.assertFalse(self.layout.environment.exists())

    def test_pip_uses_managed_python_and_hashed_lock_without_activation(self):
        self.inputs()
        probe = self.fake_environment()
        with patch.object(bootstrap, "run", side_effect=[probe, "pip 25", ""]) as run:
            bootstrap.provision_python(self.layout, self.tools)
        self.assertEqual(run.call_args.args[0], [str(self.layout.python), "-m", "pip", "install",
                         "--require-hashes", "-r", str(self.layout.root / "requirements-dev.txt")])
        self.assertEqual(run.call_args.kwargs["cwd"], self.layout.root)

    def test_pip_installer_seeds_pip_in_an_existing_uv_environment(self):
        self.inputs()
        probe = self.fake_environment()
        with patch.object(bootstrap, "run", side_effect=[probe,
                          bootstrap.BootstrapError("No module named pip"), "", ""]) as run:
            bootstrap.provision_python(self.layout, self.tools)
        self.assertEqual(run.call_args_list[2].args[0],
                         [str(self.layout.python), "-m", "ensurepip", "--upgrade"])
        self.assertIn("--require-hashes", run.call_args_list[3].args[0])

    def test_uv_frozen_install_uses_project_venv_and_no_python_downloads(self):
        self.write("pyproject.toml")
        self.write("uv.lock")
        probe = self.fake_environment()
        with patch.object(bootstrap, "run", side_effect=[probe, ""]) as run:
            bootstrap.provision_python(self.layout, bootstrap.Prerequisites("npm", "uv", "/uv"))
        self.assertEqual(run.call_args.args[0], ["/uv", "sync", "--frozen", "--project",
                         str(self.layout.root), "--python", str(self.layout.python)])
        self.assertEqual(run.call_args.kwargs["env"]["UV_PROJECT_ENVIRONMENT"], str(self.layout.environment))
        self.assertEqual(run.call_args.kwargs["env"]["UV_PYTHON_DOWNLOADS"], "never")

    def test_initial_environment_creation_uses_invoking_python(self):
        self.inputs()
        with patch.object(bootstrap, "run") as run, patch.object(bootstrap, "validate_environment"):
            bootstrap.provision_python(self.layout, self.tools)
        self.assertEqual(run.call_args_list[0].args[0],
                         [bootstrap.sys.executable, "-m", "venv", str(self.layout.environment)])

    def test_invalid_environment_is_never_deleted(self):
        self.inputs()
        sentinel = self.write(".venv/keep.txt", "user data")
        with patch.object(bootstrap, "run") as run, \
             self.assertRaisesRegex(bootstrap.BootstrapError, "Move .venv aside"):
            bootstrap.provision_python(self.layout, self.tools)
        run.assert_not_called()
        self.assertEqual(sentinel.read_text(), "user data")

    def test_environment_probe_rejects_system_and_unsupported_python(self):
        self.fake_environment()
        for info in ({"version": [3, 11], "prefix": str(self.layout.environment), "base_prefix": "/base"},
                     {"version": [3, 13], "prefix": "/base", "base_prefix": "/base"},
                     {"version": [3, 13], "prefix": "/other/venv", "base_prefix": "/base"}):
            with self.subTest(info=info), patch.object(bootstrap, "run", return_value=json.dumps(info)), \
                 self.assertRaisesRegex(bootstrap.BootstrapError, "incompatible or damaged"):
                bootstrap.validate_environment(self.layout)

    def test_configuration_has_unique_secret_and_local_debug(self):
        self.template()
        bootstrap.provision_configuration(self.layout)
        first = (self.layout.root / ".env").read_text()
        self.assertIn("DJANGO_DEBUG=True", first)
        secret = first.split("DJANGO_SECRET_KEY=", 1)[1].splitlines()[0]
        self.assertGreaterEqual(len(secret), 50)
        (self.layout.root / ".env").unlink()
        bootstrap.provision_configuration(self.layout)
        self.assertNotEqual(first, (self.layout.root / ".env").read_text())
        if os.name != "nt":
            self.assertEqual((self.layout.root / ".env").stat().st_mode & 0o777, 0o600)

    def test_repeated_setup_preserves_config_and_database_bytes(self):
        self.inputs()
        config = self.write(".env", "DJANGO_SECRET_KEY=my existing secret\nDJANGO_DEBUG=False\n")
        database = self.write("db.sqlite3", "existing database fixture")
        before = config.read_bytes(), database.read_bytes()
        with patch.object(bootstrap, "provision_python"), patch.object(bootstrap, "run"):
            bootstrap.setup(self.layout, self.tools)
            bootstrap.setup(self.layout, self.tools)
        self.assertEqual((config.read_bytes(), database.read_bytes()), before)

    def test_malformed_template_does_not_write_config(self):
        self.write(".env.example", "DJANGO_DEBUG=True\n")
        with self.assertRaisesRegex(bootstrap.BootstrapError, "exactly one DJANGO_SECRET_KEY"):
            bootstrap.provision_configuration(self.layout)
        self.assertFalse((self.layout.root / ".env").exists())

    def test_npm_failure_stops_before_migrations_and_is_recoverable(self):
        self.inputs()
        with patch.object(bootstrap, "provision_python"), \
             patch.object(bootstrap, "run", side_effect=bootstrap.BootstrapError("npm failure")), \
             patch.object(bootstrap, "finish_setup") as finish, \
             self.assertRaisesRegex(bootstrap.BootstrapError, "npm failure"):
            bootstrap.setup(self.layout, self.tools)
        finish.assert_not_called()
        original = (self.layout.root / ".env").read_bytes()
        with patch.object(bootstrap, "provision_python"), patch.object(bootstrap, "run"):
            bootstrap.setup(self.layout, self.tools)
        self.assertEqual(original, (self.layout.root / ".env").read_bytes())

    def test_frontend_installs_build_tools_with_inherited_production_environment(self):
        with patch.dict(os.environ, {"NODE_ENV": "production", "npm_config_omit": "dev"}), \
             patch.object(bootstrap, "run") as run:
            bootstrap.provision_frontend(self.layout, self.tools)
            self.assertEqual(os.environ["NODE_ENV"], "production")
        run.assert_called_once_with([self.tools.npm, "ci", "--include=dev"], cwd=self.layout.frontend)

    def test_migration_failure_never_builds_or_prints_success(self):
        self.inputs()
        output = io.StringIO()
        with patch.object(bootstrap, "provision_python"), \
             patch.object(bootstrap, "provision_frontend"), \
             patch.object(bootstrap, "run", side_effect=bootstrap.BootstrapError("migration failure")) as run, \
             contextlib.redirect_stdout(output), self.assertRaises(bootstrap.BootstrapError):
            bootstrap.setup(self.layout, self.tools)
        self.assertEqual(run.call_count, 1)
        self.assertNotIn("Setup complete", output.getvalue())

    def test_finish_order_and_frontend_working_directory(self):
        with patch.object(bootstrap, "run") as run:
            bootstrap.finish_setup(self.layout, self.tools)
        self.assertEqual([call.args[0] for call in run.call_args_list], [
            [str(self.layout.python), "manage.py", "migrate", "--noinput"],
            [self.tools.npm, "run", "build"], [str(self.layout.python), "manage.py", "check"]])
        self.assertEqual(run.call_args_list[1].kwargs["cwd"], self.layout.frontend)

    def test_diagnostics_hide_secrets_and_write_nothing(self):
        self.write(".env", "DJANGO_SECRET_KEY=DO-NOT-PRINT-ME\n")
        before = {p: p.read_bytes() for p in self.layout.root.rglob("*") if p.is_file()}
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            bootstrap.diagnostics(self.layout, self.tools)
        self.assertNotIn("DO-NOT-PRINT-ME", output.getvalue())
        self.assertEqual(before, {p: p.read_bytes() for p in self.layout.root.rglob("*") if p.is_file()})

    def test_run_keeps_paths_as_individual_arguments(self):
        command = ["/executable with spaces/python", "manage.py", "check"]
        with patch.object(bootstrap.subprocess, "run", return_value=subprocess.CompletedProcess(command, 0)) as run:
            bootstrap.run(command, cwd=self.layout.root)
        self.assertEqual(run.call_args.args, (command,))
        self.assertNotIn("shell", run.call_args.kwargs)

    def test_cli_output_survives_ascii_and_legacy_windows_streams(self):
        for encoding in ("ascii", "cp1252"):
            output_bytes = io.BytesIO()
            error_bytes = io.BytesIO()
            output = io.TextIOWrapper(output_bytes, encoding=encoding, write_through=True)
            errors = io.TextIOWrapper(error_bytes, encoding=encoding, write_through=True)
            command = ["/project-\u6d4b\u8bd5/python", "--version"]
            with self.subTest(encoding=encoding), \
                 patch.object(bootstrap.sys, "stdout", output), \
                 patch.object(bootstrap.sys, "stderr", errors), \
                 patch.object(bootstrap, "prerequisites", return_value=self.tools), \
                 patch.object(bootstrap, "diagnostics", side_effect=lambda *args: bootstrap.run(command)), \
                 patch.object(bootstrap.subprocess, "run", return_value=subprocess.CompletedProcess(command, 0)):
                self.assertEqual(bootstrap.main(["check"]), 0)
            self.assertIn(b"> /project-\\u6d4b\\u8bd5/python --version", output_bytes.getvalue())
            with patch.object(bootstrap.sys, "stdout", output), \
                 patch.object(bootstrap.sys, "stderr", errors), \
                 patch.object(bootstrap, "prerequisites", side_effect=bootstrap.BootstrapError("Missing /project-\u6d4b\u8bd5/npm")):
                self.assertEqual(bootstrap.main(["check"]), 1)
            self.assertIn(b"Missing /project-\\u6d4b\\u8bd5/npm", error_bytes.getvalue())
            output.close()
            errors.close()

    def test_subprocess_failure_reports_exit_code_without_captured_secrets(self):
        with patch.object(bootstrap.subprocess, "run", side_effect=subprocess.CalledProcessError(
                7, ["python"], stderr="DO-NOT-PRINT-ME")), \
             self.assertRaisesRegex(bootstrap.BootstrapError, "exit code 7") as error:
            bootstrap.run(["python"], cwd=self.layout.root, capture=True)
        self.assertNotIn("DO-NOT-PRINT-ME", str(error.exception))


if __name__ == "__main__":
    unittest.main()
