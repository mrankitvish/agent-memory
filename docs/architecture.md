# Architecture Overview

Agent Memory is built with a focus on simplicity, speed, and privacy. It runs entirely locally on your machine.

## System Components

### 1. Backend Server
- **Framework:** Written in Python using **FastAPI**.
- **MCP Server:** Exposes the Model Context Protocol endpoints over SSE (`/mcp/`) allowing AI agents to interact with the database.
- **API:** Provides REST endpoints for the local browser UI to query the 3D graph and perform CRUD operations.

### 2. Storage & Memory Engine
- **Metadata Database:** **SQLite** is used to store structured metadata (Namespaces, Tags, Titles, Memory Types, Timestamps).
- **Vector Database:** **ChromaDB** is used to store and search the dense vector embeddings of the memory text. 
- **Embedder:** Utilizes `sentence-transformers` running locally to generate embeddings. No data is sent to external API providers (like OpenAI) for embedding.

### 3. Frontend Dashboard
- **Technologies:** Vanilla JavaScript, HTML, and CSS. No complex build pipelines (like React/Next.js) are strictly required for runtime.
- **3D Graph:** Powered by **Three.js** and `d3-force-3d`. The graph visualizes relationships dynamically; nodes are memories and edges represent shared tags.

## Data Flow

1. An Agent calls the `save_memory` MCP tool.
2. The Backend chunks the text, passes it through the local embedding model, and stores the vectors in ChromaDB.
3. The metadata (tags, namespace) is saved in SQLite.
4. When the user opens the Local UI, the UI fetches the graph state from the FastAPI backend and renders the 3D force-directed graph.
