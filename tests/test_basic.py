import ast
from pathlib import Path
import unittest

from agent_memory import __version__


def test_package_version():
    assert __version__ == "0.1.0"


def test_memory_model_defaults():
    from agent_memory.memory_models import MemoryEntry, MemoryType

    item = MemoryEntry(content="User likes concise answers.")
    assert item.namespace == "default"
    assert item.memory_type == MemoryType.SEMANTIC
    assert "User likes concise answers." in item.content


class IngestionScopeTests(unittest.TestCase):
    def test_supported_source_types(self):
        from agent_memory.models import SourceType

        self.assertEqual({source.value for source in SourceType}, {"text"})

    def test_ingestion_tool_surface(self):
        import agent_memory

        package_dir = Path(agent_memory.__file__).parent
        tree = ast.parse((package_dir / "mcp/tools/ingestion.py").read_text(encoding="utf-8"))
        registration = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "register_ingestion_tools"
        )
        tools = {
            node.name for node in registration.body
            if isinstance(node, ast.FunctionDef) and node.decorator_list
        }
        self.assertEqual(tools, {"save_memory"})

    def test_removed_runtime_references(self):
        import agent_memory

        package_dir = Path(agent_memory.__file__).parent
        for source in package_dir.rglob("*.py"):
            with self.subTest(source=source.name):
                content = source.read_text(encoding="utf-8").lower()
                self.assertNotIn("upload", content)
                self.assertNotIn("youtube", content)

    def test_local_server_defaults(self):
        from agent_memory.config import Settings

        self.assertEqual(Settings().host, "127.0.0.1")
        self.assertEqual(Settings().port, 8090)


if __name__ == "__main__":
    unittest.main()
