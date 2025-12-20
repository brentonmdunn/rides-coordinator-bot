"""utils/parsing.py"""

import re
from datetime import datetime, time

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


def parse_time(time_str: str) -> time:
    """Parses a flexible string into a datetime.time object.

    Handles weird spacing, capitalization, and both 12-hour (AM/PM/A/P)
    and 24-hour formats. If AM/PM (or A/P) is missing, 24-hour time is assumed.

    Args:
        time_str: A string representing the time (e.g., "14:30", " 1 : 30 p ", "9a").

    Returns:
        datetime.time: The parsed time object.

    Raises:
        ValueError: If the string cannot be parsed into a valid time.
    """
    # 1. Normalize: Convert to lowercase and remove ALL spaces
    #    Example: " 1 : 30  P " -> "1:30p"
    cleaned_str = time_str.strip().lower().replace(" ", "")

    # 2. Normalize suffixes: Handle 'a' -> 'am' and 'p' -> 'pm'
    #    We check if it ends with just 'a' or 'p' to support shorthand.
    if cleaned_str.endswith("a") and not cleaned_str.endswith("ea"):
        # Note: "ea" check is just a safety against words, though unlikely in time strings.
        # If it ends in 'a' (like '10a'), make it '10am'
        cleaned_str += "m"
    elif cleaned_str.endswith("p"):
        # If it ends in 'p' (like '10p'), make it '10pm'
        cleaned_str += "m"

    # 3. Determine if we are looking for AM/PM format or 24-hour format
    is_12_hour = "am" in cleaned_str or "pm" in cleaned_str

    # 4. Define allowed formats based on the presence of am/pm
    formats = ["%I:%M%p", "%I%p"] if is_12_hour else ["%H:%M", "%H"]

    # 5. Attempt to parse
    for fmt in formats:
        try:
            return datetime.strptime(cleaned_str, fmt).time()
        except ValueError:
            continue

    raise ValueError(f"Could not parse time string: '{time_str}'")


def column_letter_to_index(letter: str) -> int:
    """Converts a column letter (e.g., "A", "AB") to a 0-based index.

    Args:
        letter: The column letter(s).

    Returns:
        The 0-based index (e.g., "A" -> 0, "B" -> 1, "AA" -> 26).
    """
    index = 0
    for char in letter.upper():
        index = index * 26 + (ord(char) - ord("A") + 1)
    return index - 1
