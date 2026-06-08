"""
Intent classifier for the #general thread-maker agent.

A single LLM turn decides whether a ``@ridebot`` message wants the bot to turn the
*replied-to* message or the *message above* into an event thread, or whether it can't
tell (in which case the caller asks the user to reply to the target message).

The LLM only classifies intent — it never touches Discord. All Discord I/O lives in the
cog/service layer so the async event loop stays in charge of network calls.
"""

import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool

from agent.ridebot_agent import llm

logger = logging.getLogger(__name__)

# Intent sources returned to the caller.
SOURCE_REPLIED = "replied_message"
SOURCE_ABOVE = "message_above"
SOURCE_CLARIFY = "clarify"

_SYSTEM_PROMPT = """You are a Discord helper whose only job is to figure out which message a \
user wants turned into a thread.

The user has mentioned the bot in a channel. Decide which message they want threaded and \
call make_event_thread with the right source:
- "replied_message": the user wants the message they replied to turned into a thread \
(e.g. "make this a thread", "thread this", "@ridebot turn this into a thread").
- "message_above": the user is NOT replying and refers to the previous message \
(e.g. "make the message above a thread", "thread the message above").

Context you are given each turn:
- is_reply: whether the user's message is a Discord reply to another message.

Rules:
- If is_reply is true, prefer "replied_message" unless the user explicitly says "above".
- If is_reply is false and the user clearly means the previous/above message, use "message_above".
- If you cannot confidently tell which message they mean, DO NOT call the tool. Instead reply \
with a single short sentence telling them to reply to the message they want turned into a thread \
and mention you."""


@tool
def make_event_thread(source: str) -> str:
    """
    Record which message should become an event thread.

    Args:
        source: Either 'replied_message' (the message the user replied to) or
                'message_above' (the message immediately before the user's command).

    Returns:
        The recorded source string.
    """
    return source


_llm_with_tools = llm.bind_tools([make_event_thread])


def classify_thread_intent(user_message: str, is_reply: bool) -> tuple[str, str | None]:
    """
    Classify a #general thread-maker request.

    Args:
        user_message: The user's message with the bot mention stripped.
        is_reply: Whether the user's message is a Discord reply.

    Returns:
        A tuple ``(source, clarification)``:
        - source is one of SOURCE_REPLIED, SOURCE_ABOVE, or SOURCE_CLARIFY.
        - clarification is the LLM's short instruction when source is SOURCE_CLARIFY,
          otherwise None.
    """
    context = f"is_reply: {is_reply}\nuser_message: {user_message}"
    response = _llm_with_tools.invoke(
        [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=context)]
    )

    for call in getattr(response, "tool_calls", []) or []:
        if call["name"] == make_event_thread.name:
            source = str(call["args"].get("source", "")).strip()
            if source in (SOURCE_REPLIED, SOURCE_ABOVE):
                logger.info(f"classify_thread_intent: source={source} is_reply={is_reply}")
                return source, None

    clarification = str(response.content).strip() or None
    logger.info(f"classify_thread_intent: clarify is_reply={is_reply}")
    return SOURCE_CLARIFY, clarification
