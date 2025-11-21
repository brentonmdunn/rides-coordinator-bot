"""utils/parsing.py"""

import re

import discord


def parse_name(text: str) -> tuple[str, str | None]:
    """Parse the input string to extract the name and username in the form "name (username)".

    Args:
        text (str): The input string to parse.

    Returns:
        tuple[str, str | None]: A tuple containing the name and username (if found).
    """
    match = re.match(r"^(.*?)\s*\((.*?)\)$", text)
    if match:
        return match.group(1), match.group(2)
    return text, None


def parse_discord_username(username: str) -> str:
    """Returns username without @ symbol.

    Args:
        username (str): The username to parse.

    Returns:
        str: The username without the leading @ symbol.
    """
    username = username.lower().strip()
    return username if "@" not in username else username[1:]


def get_first_name(name: str) -> str:
    """
    Returns first name of person. Works for both "fname" and "fname ... lname" formats.

    Args:
        name: Name to parse.

    Returns:
        First name of person.
    """
    return name.split()[0]


def get_last_name(name: str) -> str | None:
    """
    Returns the last name of the person.

    Args:
        name: Name to parse.

    Returns:
        Last name of person. Returns `None` if `name="fname"`, returns `"mname lname"`
        if `name="fname mname lname"`.
    """
    name_parts = name.split()
    if len(name_parts) > 1:
        return " ".join(name_parts[1:])
    return None


def get_message_and_embed_content(
    message: discord.Message, message_content: bool = True, embed_content: bool = True
) -> str:
    """
    Combines the text in message.content and of any embeds.

    Args:
        message (discord.Message): The message to extract content from.
        message_content (bool, optional): Whether to include the message content. Defaults to True.
        embed_content (bool, optional): Whether to include the embed content. Defaults to True.

    Returns:
        str: The combined text content.
    """
    # Gather lowercase text from content and embeds
    text_blobs = []

    # Raw content
    if message.content and message_content:
        text_blobs.append(message.content.lower())

    # Embeds text
    if embed_content:
        for embed in message.embeds:
            if embed.title:
                text_blobs.append(embed.title.lower())
            if embed.description:
                text_blobs.append(embed.description.lower())
            for field in embed.fields:
                text_blobs.append(field.name.lower())
                text_blobs.append(field.value.lower())

    return " ".join(text_blobs)
