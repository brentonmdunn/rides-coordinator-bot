"""
Run FastAPI + Discord Bot

Entry point to run the FastAPI application with integrated Discord bot.
"""

import uvicorn

from api.constants import API_HOST, API_PORT

if __name__ == "__main__":
    uvicorn.run("api.app:app", host=API_HOST, port=API_PORT, reload=False, log_level="info")
