# MCP Server & In-Cluster LLM / KubeAI Integration

This repository contains an application setup connecting a local LLM running in Kubernetes (via KubeAI or Ollama) to an **MCP (Model Context Protocol) Server** and an **API Backend**.

## Architecture Overview

```
 ┌────────────────┐     OpenAI API    ┌──────────────────────────────────┐
 │   mcp-agent    │ ────────────────> │ KubeAI Service (qwen-tiny model) │
 └───────┬────────┘                   └──────────────────────────────────┘
         │
         │ SSE Transport
         v
 ┌────────────────┐     HTTP POST     ┌──────────────────────────────────┐
 │   mcp-server   │ ────────────────> │   mcp-api-backend (Logs Hello)   │
 └────────────────┘                   └──────────────────────────────────┘
```

1. **`api_backend/`**: Simple FastAPI service. Logs `"Hello World!"` to stdout whenever `POST /api/hello` is invoked.
2. **`mcp_server/`**: Python MCP server using `mcp.server.sse.SseServerTransport`. Exposes `call_hello_api` tool. When called by the agent/LLM, it makes an HTTP request to the API backend.
3. **`mcp_agent/`**: In-cluster Python runner. Connects via SSE to `mcp-server`, discovers tools, sends prompt + tools to KubeAI (`qwen-tiny`), executes the returned tool call via MCP, and prints the LLM's final response.

---

## Technical Details

- **Fast Package Management**: All container images use [`uv`](https://github.com/astral-sh/uv) (`ghcr.io/astral-sh/uv:python3.11-bookworm-slim`) for fast Python dependency installation.
- **Transports**: `mcp.server.sse` over HTTP (`/sse` & `/messages`), ideal for network-decoupled microservices inside Kubernetes.
- **Multi-Arch Support**: Docker images are built for both `linux/amd64` and `linux/arm64` (Raspberry Pi 5 compatible).

---

## Running & Testing

### Option A: Local Testing with Docker Compose

To test locally:

```bash
docker compose up --build
```

Each service reads its configuration from its local `.env` file (copied from `.env.example`).

### Option B: Deploying to Kubernetes Cluster

1. **Build container images** (or push to your container registry):
   ```bash
   docker build -t mcp-api-backend:latest ./api_backend
   docker build -t mcp-server:latest ./mcp_server
   docker build -t mcp-agent:latest ./mcp_agent
   ```

2. **Verify Execution**:
   - Check `mcp-api-backend` logs:
     ```bash
     kubectl logs -n mcp-test -l app=mcp-api-backend -f
     ```
     You will see `"Hello World! API called at <timestamp>"` when the LLM decides to call the tool.
   - Check `mcp-agent` logs:
     ```bash
     kubectl logs -n mcp-test -l app=mcp-agent -f
     ```
