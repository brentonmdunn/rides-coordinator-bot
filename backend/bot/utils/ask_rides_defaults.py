"""
Default title/body/color templates for editable ask-rides messages.

Single source of truth for both the scheduled job's fallback and the API's
pristine/default state. See DESIGN.ask-rides-messages.md.
"""

from dataclasses import dataclass

from bot.core.enums import AskRidesMessageType, EmbedColorChoice, Emoji


@dataclass(frozen=True)
class MessageTemplate:
    """A title/body/color/reactions template. Body and title may contain `{date}`/`{ping}` tokens."""

    title: str
    body: str
    color: EmbedColorChoice
    reactions: tuple[str, ...]


DEFAULT_TEMPLATES: dict[AskRidesMessageType, MessageTemplate] = {
    AskRidesMessageType.WEDNESDAY_FELLOWSHIP: MessageTemplate(
        title="Rides to Wednesday Fellowship",
        body=(
            "React to this message if you need a ride for Wednesday college fellowship "
            "{date} (leave between 7 and 7:10pm)!"
        ),
        color=EmbedColorChoice.TEAL,
        reactions=(Emoji.FRIDAY_FELLOWSHIP,),
    ),
    AskRidesMessageType.FRIDAY_FELLOWSHIP: MessageTemplate(
        title="Rides to Friday Fellowship",
        body=(
            "React to this message if you need a ride for Friday night fellowship "
            "{date} (leave between 7 and 7:10pm)!"
        ),
        color=EmbedColorChoice.PINK,
        reactions=(Emoji.FRIDAY_FELLOWSHIP,),
    ),
    AskRidesMessageType.SUNDAY_SERVICE: MessageTemplate(
        title="Rides to Sunday Service",
        body=(
            "React to this message if you need a ride for Sunday service {date} "
            "(leave between 10 and 10:10am)!\n\n"
            "🍔 = ride to church, lunch, and back to campus/apt (arrive back ~2:30pm)\n"
            "🏠 = ride to church and back to campus/apt (arrive back ~1:00pm)\n"
            "✳️ = something else (please DM {ping})"
        ),
        color=EmbedColorChoice.BLUE,
        reactions=(Emoji.LUNCH, Emoji.NO_LUNCH, Emoji.SOMETHING_ELSE),
    ),
    AskRidesMessageType.SUNDAY_CLASS: MessageTemplate(
        title="Rides to Bible Theology Class",
        body=(
            "React to this message if you need a ride to Bible Theology Class on Sunday "
            "{date} (leave between 8:30 and 8:40am). "
            "Make sure to also react to the message below for 🍔, 🏠, or ✳️."
        ),
        color=EmbedColorChoice.BLURPLE,
        reactions=(Emoji.SUNDAY_CLASS,),
    ),
}

# Cap on how many reaction emojis a template may configure. Discord allows up
# to 20 unique reactions per message; keep a margin for users' own reactions.
MAX_REACTIONS = 10

# Placeholders each message type's title/body may reference. Used to validate
# saved templates so an unsupported token is rejected at save time.
ALLOWED_PLACEHOLDERS: dict[AskRidesMessageType, set[str]] = {
    AskRidesMessageType.WEDNESDAY_FELLOWSHIP: {"date"},
    AskRidesMessageType.FRIDAY_FELLOWSHIP: {"date"},
    AskRidesMessageType.SUNDAY_SERVICE: {"date", "ping"},
    AskRidesMessageType.SUNDAY_CLASS: {"date"},
}
