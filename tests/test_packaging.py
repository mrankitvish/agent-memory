import contextlib
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class PackagingTests(unittest.TestCase):
    def test_store_lock_rejects_second_owner_and_releases(self):
        from agent_memory.runtime import store_lock
        with tempfile.TemporaryDirectory() as directory:
            metadata = Path(directory) / "metadata.db"
            chroma = Path(directory) / "chroma"
            with store_lock(metadata, chroma):
                with self.assertRaises(RuntimeError):
                    with store_lock(metadata, chroma):
                        pass
            with store_lock(metadata, chroma):
                pass

    def test_port_conflict_fails_before_model_load(self):
        import socket
        from types import SimpleNamespace
        from agent_memory.main import serve
        from agent_memory.log import get_logger
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            args = SimpleNamespace(host="127.0.0.1", port=listener.getsockname()[1], transport="http")
            with self.assertRaisesRegex(RuntimeError, "Choose another --port"):
                serve(args, get_logger("test"))

    def test_launcher_sets_local_model_before_server_import(self):
        launcher_path = Path(__file__).parents[1] / "packaging" / "launcher.py"
        spec = importlib.util.spec_from_file_location("binary_launcher", launcher_path)
        launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(launcher)
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / "models" / "all-MiniLM-L6-v2"
            model.mkdir(parents=True)
            (model / "modules.json").write_text("[]", encoding="utf-8")
            with patch.object(launcher, "__file__", str(Path(directory) / "launcher.py")), \
                    patch.object(launcher.sys, "frozen", True, create=True), \
                    patch.dict(os.environ, {}, clear=True):
                launcher.configure_bundle()
                self.assertEqual(Path(os.environ["AGENT_MEMORY_EMBEDDING_MODEL"]).resolve(), model.resolve())
                self.assertEqual(os.environ["HF_HUB_OFFLINE"], "1")

    def test_application_logs_do_not_pollute_stdio(self):
        from agent_memory.log import setup_logging, get_logger
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            setup_logging()
            get_logger("packaging-test").info("stdio-safe")
        setup_logging()
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("stdio-safe", stderr.getvalue())