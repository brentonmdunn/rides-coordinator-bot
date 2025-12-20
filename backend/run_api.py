"""
Run FastAPI + Discord Bot

Entry point to run the FastAPI application with integrated Discord bot.
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
