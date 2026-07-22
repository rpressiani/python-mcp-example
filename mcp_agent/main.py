import asyncio
import json
import logging
import os
import httpx
from openai import AsyncOpenAI
from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionToolMessageParam,
    ChatCompletionToolParam,
)
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("mcp_agent")

MCP_SERVER_SSE_URL = os.getenv("MCP_SERVER_SSE_URL", "http://mcp-server.mcp-test.svc.cluster.local:8001/sse")
KUBEAI_URL = os.getenv("KUBEAI_URL", "http://kubeai.kubeai.svc.cluster.local/openai/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen-tiny")
PROMPT = os.getenv("PROMPT", "Please call the hello world API tool and let me know the response.")

async def run_agent():
    logger.info("==================================================")
    logger.info(f"Starting MCP Agent runner...")
    logger.info(f"Connecting to MCP SSE Server at: {MCP_SERVER_SSE_URL}")
    logger.info(f"KubeAI OpenAI Endpoint: {KUBEAI_URL} (Model: {MODEL_NAME})")
    logger.info("==================================================")

    # Initialize OpenAI client pointing to KubeAI endpoint
    openai_client = AsyncOpenAI(
        base_url=KUBEAI_URL,
        api_key="not-needed"  # KubeAI local cluster endpoint does not require an API key
    )

    async with sse_client(MCP_SERVER_SSE_URL) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            logger.info("Successfully connected to MCP Server!")

            # 1. Discover tools from MCP server
            mcp_tools = await session.list_tools()
            logger.info(f"Discovered {len(mcp_tools.tools)} tool(s) from MCP server:")
            for tool in mcp_tools.tools:
                logger.info(f" - {tool.name}: {tool.description}")

            # Format tools for OpenAI client compatibility
            openai_tools: list[ChatCompletionToolParam] = []
            for tool in mcp_tools.tools:
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": tool.inputSchema or {"type": "object", "properties": {}},
                    }
                })

            # 2. Query LLM via KubeAI with tool definition attached
            messages: list[ChatCompletionMessageParam] = [{"role": "user", "content": PROMPT}]
            logger.info(f"Sending user prompt to LLM '{MODEL_NAME}': '{PROMPT}'")

            response = await openai_client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                tools=openai_tools,
                tool_choice="auto"
            )

            assistant_msg = response.choices[0].message
            logger.info(f"LLM Response message: {assistant_msg}")

            # 3. Check for tool call requests from LLM
            if assistant_msg.tool_calls:
                messages.append(assistant_msg.model_dump(exclude_none=True))  # type: ignore[arg-type]
                for tool_call in assistant_msg.tool_calls:
                    if tool_call.type != "function":
                        continue
                    fn_name = tool_call.function.name
                    fn_args_str = tool_call.function.arguments or "{}"
                    fn_args = json.loads(fn_args_str) if fn_args_str else {}

                    logger.info(f"LLM requested tool execution: '{fn_name}' with args: {fn_args}")

                    # Invoke MCP tool via MCP session
                    mcp_result = await session.call_tool(fn_name, fn_args)
                    result_text = "\n".join([c.text for c in mcp_result.content if c.type == "text"])
                    logger.info(f"MCP tool '{fn_name}' execution result: {result_text}")

                    # Append tool result back to message history
                    messages.append(
                        ChatCompletionToolMessageParam(
                            role="tool",
                            tool_call_id=tool_call.id,
                            content=result_text,
                        )
                    )

                # 4. Get final synthesis from LLM
                final_response = await openai_client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages,
                )
                logger.info("==================================================")
                logger.info(f"Final LLM Response:\n{final_response.choices[0].message.content}")
                logger.info("==================================================")
            else:
                logger.info(f"Direct LLM Response (no tool call triggered):\n{assistant_msg.content}")

if __name__ == "__main__":
    asyncio.run(run_agent())
