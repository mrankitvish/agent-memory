<div align="center">
  <h1>🧠 Agent Memory</h1>
  <p><b>Persistent, interactive memory for MCP-powered AI Agents</b></p>
</div>

---

**Agent Memory** provides a local, text-only persistent memory system for MCP (Model Context Protocol) agents. It comes with a beautiful local browser workspace and an interactive 3D memory graph to visualize how your agents store, connect, and retrieve information.

## ✨ Features

- **🔌 Native MCP Integration:** Exposes tools like `save_memory`, `recall_memories`, and `search_memories` directly to your MCP agents.
- **🌌 3D Knowledge Graph:** Visualize relationships between memories using an interactive force-directed 3D graph.
- **🔍 Semantic Search:** Powered by local embeddings and ChromaDB for lightning-fast, relevant recall.
- **💻 Local Dashboard:** A clean UI to manually create, edit, search, and manage what your agent knows.
- **🔒 Privacy First:** Runs completely locally. No cloud dependencies, no data leaving your machine.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11 or higher
- Node.js (only required for UI development)

### Installation

Clone the repository and install the dependencies:

```bash
# Clone the repo
git clone https://github.com/mrankitvish/agent-memory.git
cd agent-memory

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the package
pip install -e .
```

### Running the Server

Start the memory server and UI:

```bash
python3 -m agent_memory.main
```

- **Dashboard:** Open [http://127.0.0.1:8090](http://127.0.0.1:8090) in your browser.
- **MCP Endpoint:** Point your MCP clients to `http://127.0.0.1:8090/mcp/`.

---

## 🛠️ MCP Tools Available

Once connected, your agent will have access to the following capabilities:

| Tool Name | Description |
| :--- | :--- |
| `save_memory` | Save a new piece of knowledge, fact, or interaction. |
| `recall_memories` | Retrieve memories based on context or semantic similarity. |
| `search_memories` | Search the memory database using literal queries. |
| `delete_memory` | Remove a specific memory from the database. |
| `list_memories` | List recent memories inside a specific namespace. |

## 🏗️ Architecture

- **Backend:** Python, FastAPI
- **Database:** SQLite (Metadata) + ChromaDB (Embeddings)
- **Frontend:** Vanilla JS, HTML, CSS with Three.js for 3D visualization
- **Protocol:** Standard MCP over HTTP/SSE

---

## 🛡️ License

This project is licensed under the terms included in the [LICENSE](LICENSE) file.
