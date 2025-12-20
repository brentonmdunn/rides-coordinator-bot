import discord

from bot.services.help_service import HelpService


def test_help_embed_structure(fake_bot):
    """Ensure HelpService returns a valid embed object."""
    service = HelpService()
    embed = service.build_help_embed(fake_bot)

    assert isinstance(embed, discord.Embed)
    assert embed.title == "Available Slash Commands"
    assert "Here are the commands" in embed.description
    assert embed.color == discord.Color.blue()
