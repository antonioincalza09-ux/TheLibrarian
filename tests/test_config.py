from __future__ import annotations

import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from src.config import load_config


class ConfigTests(unittest.TestCase):
    def test_defaults_are_safe(self) -> None:
        with isolated_cwd(), mock.patch.dict(os.environ, {}, clear=True):
            config = load_config()

        self.assertEqual(config.provider, "deterministic")
        self.assertTrue(config.dry_run)
        self.assertEqual(config.output_directory, ".thelibrarian/reports")
        self.assertEqual(config.privacy_mode, "metadata-only")

    def test_root_config_overrides_defaults(self) -> None:
        with isolated_cwd(), tempfile.TemporaryDirectory() as temp_directory, mock.patch.dict(os.environ, {}, clear=True):
            root = Path(temp_directory)
            (root / ".thelibrarian").mkdir()
            (root / ".thelibrarian" / "config.toml").write_text(
                "[thelibrarian]\nprovider = \"ollama\"\nmodel = \"llama3.1\"\n",
                encoding="utf-8",
            )

            config = load_config(root=root)

        self.assertEqual(config.provider, "ollama")
        self.assertEqual(config.model, "llama3.1")

    def test_explicit_config_overrides_root_config(self) -> None:
        with isolated_cwd(), tempfile.TemporaryDirectory() as temp_directory, mock.patch.dict(os.environ, {}, clear=True):
            root = Path(temp_directory)
            (root / ".thelibrarian").mkdir()
            (root / ".thelibrarian" / "config.toml").write_text(
                "[thelibrarian]\nprovider = \"deterministic\"\n",
                encoding="utf-8",
            )
            config_path = root / "chosen.toml"
            config_path.write_text(
                "[thelibrarian]\nprovider = \"openai-compatible\"\nendpoint = \"https://example.test/v1\"\n",
                encoding="utf-8",
            )

            config = load_config(root=root, config_path=config_path)

        self.assertEqual(config.provider, "openai-compatible")
        self.assertEqual(config.endpoint, "https://example.test/v1")

    def test_environment_overrides_config_file(self) -> None:
        with isolated_cwd(), tempfile.TemporaryDirectory() as temp_directory:
            config_path = Path(temp_directory) / "config.toml"
            config_path.write_text("[thelibrarian]\nprovider = \"deterministic\"\n", encoding="utf-8")

            with mock.patch.dict(os.environ, {"THELIBRARIAN_PROVIDER": "ollama"}, clear=True):
                config = load_config(config_path=config_path)

        self.assertEqual(config.provider, "ollama")

    def test_cli_overrides_environment(self) -> None:
        with isolated_cwd(), mock.patch.dict(os.environ, {"THELIBRARIAN_PROVIDER": "ollama"}, clear=True):
            config = load_config(overrides={"provider": "deterministic"})

        self.assertEqual(config.provider, "deterministic")


@contextmanager
def isolated_cwd():
    previous = Path.cwd()
    with tempfile.TemporaryDirectory() as temp_directory:
        os.chdir(temp_directory)
        try:
            yield Path(temp_directory)
        finally:
            os.chdir(previous)


if __name__ == "__main__":
    unittest.main()
