# Source Code

## `cogs/`
All slash commands are organized by category into a a file in `cogs/`. These files are automatically loaded into the bot on startup, so no need to register a new slash command when you create it. `help.py` also auto-generates the `/help` command, so make sure to put descriptions when creating slash commands.

## `disabled/`
Old slash commands and jobs that have been retired.

## `jobs/`
Scheduled jobs to be run at certain times. They are loaded by `/src/cogs/job_scheduler.py`.

## `utils/`
Helpful utility functions.

## `enums.py`
Commonlt used channel IDs and role IDs are defined here.