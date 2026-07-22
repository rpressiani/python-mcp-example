import logging
import os
import httpx
import uvicorn

from mcp.server import Server
from mcp.server.sse import SseServerTransport
import mcp.types as types
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("mcp_server")

API_BACKEND_URL = os.getenv("API_BACKEND_URL", "http://mcp-api-backend.mcp-test.svc.cluster.local:8000/api/hello")

server = Server("mcp-hello-server")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="call_hello_api",
            description="Calls the Hello World backend API to trigger a hello log message and return the backend response.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    if name != "call_hello_api":
        raise ValueError(f"Unknown tool: {name}")

    logger.info(f"MCP Server invoking API Backend at: {API_BACKEND_URL}")
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(API_BACKEND_URL, timeout=10.0)
            res.raise_for_status()
            result_text = res.text
            logger.info(f"API Backend call successful. Response: {result_text}")
    except Exception as e:
        logger.error(f"Failed to call API Backend: {e}")
        result_text = f"{{\"status\": \"error\", \"detail\": \"{str(e)}\"}}"

    return [types.TextContent(type="text", text=result_text)]

sse = SseServerTransport("/messages/")

class SSEApp:
    async def __call__(self, scope, receive, send):
        async with sse.connect_sse(scope, receive, send) as streams:
            await server.run(streams[0], streams[1], server.create_initialization_options())

class MessagesApp:
    async def __call__(self, scope, receive, send):
        await sse.handle_post_message(scope, receive, send)

async def handle_health(request):
    return JSONResponse({"status": "ok"})

app = Starlette(
    debug=True,
    routes=[
        Route("/sse", endpoint=SSEApp()),
        Route("/messages", endpoint=MessagesApp(), methods=["POST"]),
        Route("/health", endpoint=handle_health, methods=["GET"]),
    ],
)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
