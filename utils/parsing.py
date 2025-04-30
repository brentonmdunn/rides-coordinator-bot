import re


def parse_name(text):
    """
    Parse the input string to extract the name and username.

    Args:
        input_string (str): The input string to parse.

    Returns:
        tuple: A tuple containing the name and username.
    """
    match = re.match(r"^(.*?)\s*\((.*?)\)$", text)
    if match:
        return match.group(1), match.group(2)
    return text, None

def parse_discord_username(username: str) -> str:
    """
    Returns username without @ symbol.
    """
    return username if "@" not in username else username[1:]