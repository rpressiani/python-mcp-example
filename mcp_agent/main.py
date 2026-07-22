import asyncio
import json
import logging
import os
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
import uvicorn
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
PORT = int(os.getenv("PORT", "8002"))

app = FastAPI(
    title="MCP Agent API",
    description="Exposes HTTP API endpoints to trigger LLM Agent execution with MCP tool integration."
)

class PromptRequest(BaseModel):
    prompt: str = "Please call the hello world API tool and let me know the response."
    model: str | None = None

class AgentResponse(BaseModel):
    response: str
    tools_used: list[str]
    model: str

async def execute_agent(prompt: str, model_name: str) -> AgentResponse:
    logger.info(f"Connecting to MCP SSE Server at: {MCP_SERVER_SSE_URL}")
    logger.info(f"KubeAI OpenAI Endpoint: {KUBEAI_URL} (Model: {model_name})")

    openai_client = AsyncOpenAI(
        base_url=KUBEAI_URL,
        api_key="not-needed"
    )

    tools_used: list[str] = []

    async with sse_client(MCP_SERVER_SSE_URL, timeout=60.0, sse_read_timeout=300.0) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            logger.info("Connected to MCP Server session.")

            # Discover tools
            mcp_tools = await session.list_tools()
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

            messages: list[ChatCompletionMessageParam] = [
                {"role": "system", "content": "You are an AI agent. When asked to call a tool or API, you MUST invoke the function using tool_calls."},
                {"role": "user", "content": prompt}
            ]
            logger.info(f"Sending prompt to LLM '{model_name}': '{prompt}'")

            response = await openai_client.chat.completions.create(
                model=model_name,
                messages=messages,
                tools=openai_tools,
                tool_choice="auto"
            )

            assistant_msg = response.choices[0].message
            logger.info(f"LLM initial response: {assistant_msg}")

            if assistant_msg.tool_calls:
                messages.append(assistant_msg.model_dump(exclude_none=True))  # type: ignore[arg-type]
                for tool_call in assistant_msg.tool_calls:
                    if tool_call.type != "function":
                        continue
                    fn_name = tool_call.function.name
                    fn_args_str = tool_call.function.arguments or "{}"
                    fn_args = json.loads(fn_args_str) if fn_args_str else {}
                    tools_used.append(fn_name)

                    logger.info(f"Executing tool '{fn_name}' with args: {fn_args}")
                    mcp_result = await session.call_tool(fn_name, fn_args)
                    result_text = "\n".join([c.text for c in mcp_result.content if c.type == "text"])

                    messages.append(
                        ChatCompletionToolMessageParam(
                            role="tool",
                            tool_call_id=tool_call.id,
                            content=result_text,
                        )
                    )

                final_response = await openai_client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                )
                final_text = final_response.choices[0].message.content or ""
            else:
                logger.warning(f"No tool calls returned by LLM '{model_name}'. Assistant output: {assistant_msg.content}")
                final_text = assistant_msg.content or ""

            return AgentResponse(
                response=final_text,
                tools_used=tools_used,
                model=model_name
            )

def unwrap_exception(e: BaseException) -> str:
    if isinstance(e, BaseExceptionGroup):
        sub_msgs = [unwrap_exception(sub) for sub in e.exceptions]
        return "; ".join(sub_msgs)
    return str(e)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/prompt", response_model=AgentResponse)
async def run_prompt(req: PromptRequest):
    model_to_use = req.model or MODEL_NAME
    try:
        res = await execute_agent(req.prompt, model_to_use)
        return res
    except Exception as e:
        detailed_err = unwrap_exception(e)
        logger.error(f"Error executing agent prompt: {detailed_err}", exc_info=True)
        raise HTTPException(status_code=500, detail=detailed_err)

@app.get("/run")
async def run_default():
    """Helper GET endpoint to trigger default prompt easily via curl or browser."""
    default_prompt = os.getenv("PROMPT", "Please call the hello world API tool and let me know the response.")
    return await run_prompt(PromptRequest(prompt=default_prompt))

if __name__ == "__main__":
    logger.info(f"Starting MCP Agent API server on port {PORT}...")
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=False)
