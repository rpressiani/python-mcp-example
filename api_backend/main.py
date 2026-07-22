import logging
from datetime import datetime, timezone
from fastapi import FastAPI

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("api_backend")

app = FastAPI(title="MCP Test API Backend")

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.api_route("/api/hello", methods=["GET", "POST"])
def say_hello():
    timestamp = datetime.now(timezone.utc).isoformat()
    logger.info(f"[{timestamp}] Hello World! API called")
    return {
        "status": "success",
        "message": "Hello World!",
        "timestamp": timestamp
    }

if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)

