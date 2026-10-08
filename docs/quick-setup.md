# Quick Setup Guide

Getting Agent Memory up and running on your local machine is quick and straightforward.

## Prerequisites
- **Python 3.11** or higher
- **Node.js** (Optional, only required if you want to modify the frontend UI)

## Installation Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/mrankitvish/agent-memory.git
   cd agent-memory
   ```

2. **Create a Python Virtual Environment:**
   ```bash
   # On macOS and Linux
   python3 -m venv .venv
   source .venv/bin/activate

   # On Windows
   python -m venv .venv
   .\.venv\Scripts\activate
   ```

3. **Install the package:**
   Install Agent Memory in editable mode so you can easily pull updates or tweak the code.
   ```bash
   pip install -e .
   ```

4. **Start the Server:**
   ```bash
   python3 -m agent_memory.main
   ```
   *Note: On the first run, the embedding model will be downloaded automatically.*

## Verifying the Installation

- **Dashboard:** Open your web browser and navigate to [http://127.0.0.1:8090](http://127.0.0.1:8090). You should see the Agent Memory UI.
- **MCP Endpoint:** Your MCP clients can connect to `http://127.0.0.1:8090/mcp/`.
