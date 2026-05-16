"""
Proof-of-concept tool-calling agent using LiteLLM.

To switch providers, change MODEL/API_BASE/API_KEY at the top of this file
and set the appropriate key in .env:

  TritonAI (current):
    MODEL   = "openai/api-gpt-oss-120b"
    API_BASE = "https://tritonai-api.ucsd.edu/v1"
    API_KEY  = os.environ["TRITON_API_KEY"]

  Gemini:
    MODEL    = "gemini/gemini-2.5-flash"
    API_BASE = None
    API_KEY  = os.environ["GOOGLE_API_KEY"]

  OpenAI:
    MODEL    = "gpt-4o-mini"
    API_BASE = None
    API_KEY  = os.environ["OPENAI_API_KEY"]

  Claude:
    MODEL    = "claude-haiku-4-5"
    API_BASE = None
    API_KEY  = os.environ["ANTHROPIC_API_KEY"]
"""

import json
import os
from pathlib import Path
import litellm
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

MODEL = "openai/api-gpt-oss-120b"
API_BASE = "https://tritonai-api.ucsd.edu/v1"
API_KEY = os.environ["TRITON_API_KEY"]

# --- Tools -----------------------------------------------------------------

def add(a: float, b: float) -> float:
    return a + b

def subtract(a: float, b: float) -> float:
    return a - b

def multiply(a: float, b: float) -> float:
    return a * b

def divide(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b

TOOL_MAP = {
    "add": add,
    "subtract": subtract,
    "multiply": multiply,
    "divide": divide,
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add",
            "description": "Add two numbers",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
                "required": ["a", "b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "subtract",
            "description": "Subtract b from a",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
                "required": ["a", "b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "multiply",
            "description": "Multiply two numbers",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
                "required": ["a", "b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "divide",
            "description": "Divide a by b",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
                "required": ["a", "b"],
            },
        },
    },
]

# --- Agent loop ------------------------------------------------------------

def _completion_with_backoff(**kwargs):
    """Wrap litellm.completion, honouring the retryDelay from 429 responses."""
    import re
    import time
    for attempt in range(5):
        try:
            return litellm.completion(**kwargs)
        except litellm.RateLimitError as e:
            if attempt == 4:
                raise
            match = re.search(r"retryDelay.*?(\d+)s", str(e))
            delay = int(match.group(1)) + 2 if match else 60
            print(f"  [rate limit] retrying in {delay}s...")
            time.sleep(delay)


def run_agent(user_message: str) -> str:
    messages = [{"role": "user", "content": user_message}]

    while True:
        response = _completion_with_backoff(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            api_base=API_BASE,
            api_key=API_KEY,
        )

        msg = response.choices[0].message
        messages.append(msg)

        if not msg.tool_calls:
            return msg.content

        for call in msg.tool_calls:
            fn_name = call.function.name
            args = json.loads(call.function.arguments)

            fn = TOOL_MAP.get(fn_name)
            if fn is None:
                result = f"Unknown tool: {fn_name}"
            else:
                try:
                    result = fn(**args)
                except Exception as e:
                    result = f"Error: {e}"

            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": str(result),
            })


# --- Entry point -----------------------------------------------------------

if __name__ == "__main__":
    prompts = [
        "What is 17 + 26?",
    ]

    for prompt in prompts:
        print(f"Q: {prompt}")
        answer = run_agent(prompt)
        print(f"A: {answer}\n")
