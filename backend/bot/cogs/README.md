# 🧩 Discord Bot Cogs

This directory contains all the modular **cogs** used by the Discord bot. Each cog is a self-contained feature or set of related commands/listeners, organized for maintainability and scalability.

---

## 📚 What Are Cogs?

Cogs are classes that group together related commands and event listeners for Discord bots using `discord.py`. They help keep the codebase modular by separating bot functionality into logical units.

Learn more: https://discordpy.readthedocs.io/en/stable/ext/commands/cogs.html

---


> ⚠️ Cogs in `../cogs_disabled/` are currently inactive or in testing.

---

## ➕ How to Add a New Cog

1. **Create a new file** in the `cogs/` directory:
   ```bash
   touch cogs/my_feature.py
   ```

2. **Define your cog** in that file:
   ```python
   from discord.ext import commands

   class MyFeature(commands.Cog):
       def __init__(self, bot):
           self.bot = bot

       @commands.command()
       async def ping(self, ctx):
           await ctx.send("Pong!")

   def setup(bot):
       bot.add_cog(MyFeature(bot))
   ```
The new file will be automatically loaded at startup.

---

## ✅ Best Practices

- Keep each cog focused on **one responsibility**.
- Use meaningful names and docstrings.
- Group related commands and listeners in the same cog.
- Avoid tight coupling with other cogs; use utility functions in `/utils`.

---

## 🧼 Naming Conventions

- Files: `snake_case.py`
- Classes: `PascalCaseCog`
- Commands: `kebab-case-command`

---

## 🛠️ Related

- [Discord.py Cog Documentation](https://discordpy.readthedocs.io/en/stable/ext/commands/cogs.html)
- Project Root [`main.py`](../main.py)

---
