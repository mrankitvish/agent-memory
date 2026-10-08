from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient


class MemoryApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from agent_memory.config import settings
        cls.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.old_paths = settings.metadata_db_path, settings.chroma_path
        settings.metadata_db_path = Path(cls.temp.name) / "metadata.db"
        settings.chroma_path = Path(cls.temp.name) / "chroma"
        from agent_memory.engine.rag_engine import RAGEngine
        from agent_memory.web import create_app
        cls.engine = RAGEngine()
        cls.client = TestClient(create_app(cls.engine, with_mcp=False), headers={"X-Memory-Client": "local-ui"})

    @classmethod
    def tearDownClass(cls):
        from agent_memory.config import settings
        cls.client.close()
        cls.engine.metadata_store._db.conn.close()
        settings.metadata_db_path, settings.chroma_path = cls.old_paths
        cls.temp.cleanup()

    def test_text_crud_search_and_graph(self):
        payload = {"title": "Release procedure", "content": "Run tests before every release.\nKeep the changelog current.",
                   "memory_type": "procedural", "tags": ["release"], "namespace": "test"}
        response = self.client.post("/api/memories", json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        first = response.json()
        self.assertEqual(first["content"], payload["content"])
        second = self.client.post("/api/memories", json={**payload, "title": "Release notes"}).json()
        other = self.client.post("/api/memories", json={**payload, "namespace": "other"}).json()
        graph = self.client.get("/api/graph?namespace=test").json()
        self.assertEqual(len(graph["nodes"]), 2)
        self.assertEqual(len(graph["links"]), 1)
        self.assertEqual(graph["links"][0]["tags"], ["release"])
        matches = self.client.get("/api/search?namespace=test&query=release%20tests").json()
        self.assertEqual({item["id"] for item in matches["items"]}, {first["id"], second["id"]})
        payload["content"] = "Updated release checklist."
        updated = self.client.put(f"/api/memories/{first['id']}", json=payload)
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["id"], first["id"])
        self.assertEqual(updated.json()["content"], payload["content"])
        self.assertEqual(updated.json()["created_at"], first["created_at"])
        self.assertEqual(self.engine.vector_store.count("test"), 2)
        for doc in (first, second, other):
            self.assertEqual(self.client.delete(f"/api/memories/{doc['id']}").status_code, 204)
        self.assertEqual(self.client.get(f"/api/memories/{first['id']}").status_code, 404)
        self.assertEqual(self.client.get("/api/graph?namespace=test").json()["nodes"], [])
        self.assertEqual(self.engine.vector_store.count("test"), 0)

    def test_validation_and_browser_security(self):
        payload = {"title": "Note", "content": "  "}
        self.assertEqual(self.client.post("/api/memories", json=payload).status_code, 422)
        payload["content"] = "Valid text"
        self.assertEqual(self.client.post("/api/memories", json={**payload, "namespace": "../bad"}).status_code, 422)
        self.assertEqual(self.client.post("/api/memories", json=payload, headers={"Origin": "https://example.com"}).status_code, 403)
        self.assertEqual(self.client.post("/api/memories", json=payload, headers={"X-Memory-Client": ""}).status_code, 403)
        self.assertEqual(self.client.get("/api/status", headers={"Host": "evil.example"}).status_code, 400)
        self.assertEqual(self.client.get("/api/status").status_code, 200)

    def test_ui_assets_and_mcp(self):
        from agent_memory.web import create_app
        import asyncio
        from fastmcp import Client
        from agent_memory.mcp.server import create_mcp_server

        with TestClient(create_app(self.engine)) as client:
            self.assertEqual(client.get("/").status_code, 200)
            for asset in ("app.js", "app.css"):
                self.assertEqual(client.get(f"/ui/{asset}").status_code, 200)
            self.assertEqual(client.get("/api/status").status_code, 200)
            response = client.post("/mcp/", headers={"Accept": "application/json, text/event-stream"}, json={
                "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                    "protocolVersion": "2025-03-26", "capabilities": {},
                    "clientInfo": {"name": "integration-test", "version": "1.0"},
                },
            })
            self.assertEqual(response.status_code, 200, response.text)

        async def verify_tools():
            async with Client(create_mcp_server(self.engine)) as client:
                names = {tool.name for tool in await client.list_tools()}
                self.assertEqual(names, {
                    "save_memory", "recall_memories", "recall_memories_with_sources",
                    "list_memories", "search_memories", "get_memory", "update_memory",
                    "delete_memory", "get_memory_status",
                })
                resources = {str(resource.uri) for resource in await client.list_resources()}
                self.assertTrue({"agent-memory://status", "agent-memory://namespaces",
                                 "agent-memory://skill"}.issubset(resources))
                skill = await client.read_resource("agent-memory://skill")
                self.assertIn("name: agent-memory", skill[0].text)
                self.assertIn("update_memory", skill[0].text)
                import json
                def data(result):
                    return json.loads(result.content[0].text)
                saved = data(await client.call_tool("save_memory", {
                    "text": "MCP preference: concise answers", "title": "MCP test",
                    "namespace": "mcp-test", "memory_type": "profile", "tags": ["test"],
                }))
                memory_id = saved["memory_id"]
                try:
                    original = data(await client.call_tool("get_memory", {"memory_id": memory_id}))
                    updated = data(await client.call_tool("update_memory", {
                        "memory_id": memory_id, "text": "MCP preference: detailed answers", "tags": [],
                    }))
                    self.assertEqual(updated["memory_id"], memory_id)
                    self.assertEqual(updated["title"], original["title"])
                    self.assertEqual(updated["created_at"], original["created_at"])
                    self.assertEqual(updated["tags"], [])
                    detail = await client.read_resource(f"agent-memory://memories/{memory_id}")
                    self.assertIn("detailed answers", detail[0].text)
                    found = data(await client.call_tool("search_memories", {"query": "detailed", "namespace": "mcp-test"}))
                    self.assertEqual(found["total"], 1)
                    listed = data(await client.call_tool("list_memories", {"namespace": "mcp-test"}))
                    self.assertEqual(listed["total"], 1)
                    for tool in ("recall_memories", "recall_memories_with_sources"):
                        result = await client.call_tool(tool, {"query": "answer preference", "namespace": "mcp-test"})
                        self.assertIn(memory_id, str(result))
                    status = data(await client.call_tool("get_memory_status", {"memory_id": memory_id}))
                    self.assertEqual(status["status"], "indexed")
                finally:
                    deleted = data(await client.call_tool("delete_memory", {"memory_id": memory_id}))
                    self.assertEqual(deleted["status"], "deleted")
                await client.read_resource("agent-memory://status")

        asyncio.run(verify_tools())


if __name__ == "__main__":
    unittest.main()