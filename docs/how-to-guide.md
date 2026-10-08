# How-To Guide

This guide walks you through using Agent Memory, both from the local UI and via MCP with your AI agents.

## 1. Using the Local Dashboard

The Agent Memory dashboard is accessible at `http://127.0.0.1:8090`. It allows you to visually inspect and manage your agent's knowledge base.

- **Creating Memories:** Click the "Add Memory" button. You can specify a title, namespace (to categorize memories), tags, and the content.
- **Visualizing the Graph:** Navigate to the 3D Graph view. Memories that share the same **tags** within the same **namespace** are physically linked together in the 3D space. You can drag nodes to explore the cluster.
- **Searching:** Use the search bar to perform semantic searches over the stored memories. The system uses local embeddings to find contextually relevant information.

## 2. Connecting an MCP Client

To allow your AI agent (like Claude Desktop) to access this memory, configure it to connect to the MCP server endpoint.

**Endpoint URL:** `http://127.0.0.1:8090/mcp/`

## 3. Using MCP Tools

Once connected, your agent will automatically have access to the following tools:

- `save_memory`: Instruct the agent to save a piece of information for later use. (e.g. *"Remember that the user prefers Python over JavaScript."*)
- `recall_memories`: Retrieve memories semantically. (e.g. *"What did the user say about their favorite programming language?"*)
- `search_memories`: Retrieve memories using literal keyword search.
- `list_memories`: List all recent memories within a specific namespace.
- `delete_memory`: Remove outdated or incorrect knowledge.

By providing these tools, your agent gains a persistent, long-term memory across isolated conversations.
