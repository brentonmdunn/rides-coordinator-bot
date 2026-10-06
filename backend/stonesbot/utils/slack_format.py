"""
Convert Slack message text to Discord markdown.

Slack sends message text in its own "mrkdwn" dialect: single-character bold and
strike markers, angle-bracket entities for links and mentions, and HTML-escaped
``&``, ``<`` and ``>``. These helpers are pure so they can be tested without
Slack; resolving user ids to names is the caller's job (see `extract_user_ids`).
"""

import html
import re

DISCORD_MESSAGE_LIMIT = 2000

# Code (fenced blocks and inline spans) and angle-bracket entities (links,
# mentions, specials) are set aside before bold/strike conversion so markers
# inside them, like the ``*`` in a URL, are never touched.
_PROTECTED_PATTERN = re.compile(r"```[\s\S]*?```|`[^`\n]+`|<[^<>\n]+>")
# Stands in for a protected token while formatting is converted. NUL never
# appears in Slack text and counts as neither a word character nor whitespace.
_PLACEHOLDER = "\x00{}\x00"
_PLACEHOLDER_PATTERN = re.compile(r"\x00(\d+)\x00")
_USER_MENTION_PATTERN = re.compile(r"<@([UW][A-Z0-9]+)(?:\|[^<>]*)?>")
# Slack marks bold/strike with one character; Discord uses two. The lookarounds
# keep snake_case, arithmetic like 2*3*4, and doubled markers from matching.
_BOLD_PATTERN = re.compile(r"(?<![\w*])\*(?=\S)([^*\n]*?\S)\*(?![\w*])")
_STRIKE_PATTERN = re.compile(r"(?<![\w~])~(?=\S)([^~\n]*?\S)~(?![\w~])")

# Slack's mass mentions: @channel, @here, @everyone (the label after | is optional).
_SPECIAL_MENTION_PATTERN = re.compile(r"<!(channel|here|everyone)(?:\|[^<>]*)?>")
# Literal "@everyone"/"@here" text. A zero-width space after the @ keeps Discord
# from treating it as a mention, so only Slack's real mass mentions can ping.
_MASS_MENTION_PATTERN = re.compile(r"@(everyone|here)\b")
_ZERO_WIDTH_SPACE = "\u200b"


def extract_user_ids(text: str) -> set[str]:
    """
    Find every Slack user id mentioned in *text*.

    Args:
        text: Raw Slack message text.

    Returns:
        The set of mentioned user ids (e.g. ``{"U012AB3CD"}``).
    """
    return set(_USER_MENTION_PATTERN.findall(text))


def _convert_entity(body: str, user_names: dict[str, str]) -> str:
    """Render the inside of one ``<...>`` Slack entity as Discord text."""
    target, _, label = body.partition("|")

    if target.startswith("@"):
        user_id = target[1:]
        return f"@{user_names.get(user_id) or label or 'unknown'}"
    if target.startswith("#"):
        return f"#{label or 'channel'}"
    if target.startswith("!"):
        # User groups (<!subteam^S123|@team>), dates (<!date^...|fallback>) and
        # anything else Slack adds later all carry a readable label.
        return label or ""
    if target.startswith("mailto:"):
        return label or target.removeprefix("mailto:")
    if label and label != target:
        return f"[{label}]({target})"
    return target


def _special_mention(token: str, pings: bool) -> str | None:
    """
    Render a Slack mass mention, or None if *token* isn't one.

    With *pings*, ``@channel``/``@everyone`` become Discord's ``@everyone`` and
    ``@here`` stays ``@here``; otherwise each keeps its Slack name.
    """
    match = _SPECIAL_MENTION_PATTERN.fullmatch(token)
    if match is None:
        return None
    kind = match.group(1)
    if not pings:
        return f"@{kind}"
    return "@here" if kind == "here" else "@everyone"


def _defuse_mass_mentions(text: str) -> str:
    """Break up literal ``@everyone``/``@here`` so Discord never pings for them."""
    return _MASS_MENTION_PATTERN.sub(f"@{_ZERO_WIDTH_SPACE}\\1", text)


def slack_to_discord(
    text: str, user_names: dict[str, str] | None = None, pings: bool = False
) -> str:
    """
    Convert Slack mrkdwn to Discord markdown.

    Links become ``[label](url)``, user and channel mentions become plain
    ``@Name``/``#channel`` text, ``*bold*`` becomes ``**bold**`` and ``~strike~``
    becomes ``~~strike~~``. Italic, quotes and code already use the same syntax
    and are left as-is, except that bold/strike conversion is skipped inside code.

    Slack's mass mentions render as ``@channel``/``@here``/``@everyone``, or with
    *pings* as Discord's ``@everyone``/``@here``. Whether they actually ping is
    up to the caller's ``allowed_mentions``. Any other ``@everyone``/``@here`` in
    the text (typed literally, in code, in a link label) is always defused with
    a zero-width space, so only a real Slack mass mention can ever ping.

    Args:
        text: Raw Slack message text.
        user_names: Display names keyed by Slack user id, for ``<@U123>`` mentions.
            Unknown ids fall back to the mention's own label, then ``@unknown``.
        pings: Render mass mentions as Discord's ``@everyone``/``@here``.

    Returns:
        The Discord-formatted text.
    """
    names = user_names or {}

    protected: list[str] = []

    def protect(match: re.Match[str]) -> str:
        token = match.group(0)
        special = _special_mention(token, pings)
        if special is not None:
            token = special
        else:
            if token.startswith("<"):
                token = _convert_entity(token[1:-1], names)
            token = _defuse_mass_mentions(html.unescape(token))
        protected.append(token)
        return _PLACEHOLDER.format(len(protected) - 1)

    converted = _PROTECTED_PATTERN.sub(protect, text)
    converted = _BOLD_PATTERN.sub(r"**\1**", converted)
    converted = _STRIKE_PATTERN.sub(r"~~\1~~", converted)
    # Slack only uses real <> for entities, so the rest is HTML-escaped. Unescape
    # before defusing so an escaped "@" can't sneak a mention past it.
    converted = _defuse_mass_mentions(html.unescape(converted))
    return _PLACEHOLDER_PATTERN.sub(lambda m: protected[int(m.group(1))], converted)


def split_message(text: str, limit: int = DISCORD_MESSAGE_LIMIT) -> list[str]:
    """
    Split *text* into chunks no longer than *limit*, preferring line breaks.

    Lines are packed greedily; a single line longer than *limit* is split at
    spaces, and a single word longer than *limit* is hard-cut.

    Args:
        text: The text to split.
        limit: Maximum length of each chunk.

    Returns:
        The chunks in order. Empty text yields an empty list.
    """
    if not text.strip():
        return []

    pieces: list[str] = []
    for line in text.split("\n"):
        if len(line) <= limit:
            pieces.append(line)
            continue
        word_chunk = ""
        for word in line.split(" "):
            while len(word) > limit:
                if word_chunk:
                    pieces.append(word_chunk)
                    word_chunk = ""
                pieces.append(word[:limit])
                word = word[limit:]
            candidate = f"{word_chunk} {word}" if word_chunk else word
            if len(candidate) <= limit:
                word_chunk = candidate
            else:
                pieces.append(word_chunk)
                word_chunk = word
        if word_chunk:
            pieces.append(word_chunk)

    chunks: list[str] = []
    current: str | None = None
    for piece in pieces:
        if current is None:
            current = piece
        elif len(current) + 1 + len(piece) <= limit:
            current = f"{current}\n{piece}"
        else:
            chunks.append(current)
            current = piece
    if current is not None:
        chunks.append(current)
    return [chunk for chunk in chunks if chunk.strip()]
