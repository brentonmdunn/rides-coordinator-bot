import logging
from dotenv import load_dotenv
import os
import asyncio
# from main import run

load_dotenv()


LOG_PATH = os.getenv("LOG_PATH")

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Print stream handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

# File handler
# file_handler = logging.FileHandler(LOG_PATH)
# file_handler.setLevel(logging.DEBUG)


formatter = logging.Formatter(
    "%(asctime)s,%(msecs)03d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s"
)

console_handler.setFormatter(formatter)
# file_handler.setFormatter(formatter)

logger.addHandler(console_handler)
# logger.addHandler(file_handler)
