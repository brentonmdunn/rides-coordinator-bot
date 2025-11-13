import discord

from app.services.help_service import HelpService


def test_help_embed_structure(fake_bot):
    embed = HelpService.build_help_embed(fake_bot)
    assert isinstance(embed, discord.Embed)
    assert "Available Slash Commands" in embed.title
