import logging
import os

from dotenv import load_dotenv

load_dotenv()


LOG_PATH = os.getenv("LOG_PATH")

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Print stream handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# File handler
# file_handler = logging.FileHandler(LOG_PATH)
# file_handler.setLevel(logging.DEBUG)


formatter = logging.Formatter(
    "%(asctime)s,%(msecs)03d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s",
)

console_handler.setFormatter(formatter)
# file_handler.setFormatter(formatter)

logger.addHandler(console_handler)
# logger.addHandler(file_handler)
