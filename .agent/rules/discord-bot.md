---
trigger: always_on
---

# Discord Bot Conventions

## Structure

- **Entry point**: `backend/main.py` — boots the bot, auto-loads cogs, starts scheduled jobs.
- **Cogs** (`bot/cogs/`): Each file is a cog with slash commands or event listeners. Auto-loaded on startup.
- **Disabled cogs** (`bot/cogs_disabled/`): Cogs that are temporarily turned off — move files here to disable.
- **Testing cogs** (`bot/cogs_testing/`): Cogs used only during development.
- **Jobs** (`bot/jobs/`): Scheduled tasks using APScheduler (e.g., asking for rides on specific days).
- **Disabled jobs** (`bot/jobs_disabled/`): Move job files here to disable.

## Enums (Single Source of Truth)

All enums are in `bot/core/enums.py`. Key enums:

- `ChannelIds` / `RoleIds` / `CategoryIds` — Discord resource IDs
- `FeatureFlagNames` — feature flag identifiers
- `JobName` — scheduled job identifiers
- `DaysOfWeek` / `DaysOfWeekNumber` — day representations
- `PickupLocations` / `CampusLivingLocations` — ride locations
- `RideType` / `AskRidesMessage` — ride-related message types

## Feature Flags

- Managed via `FeatureFlagNames` enum and `feature_flags_repository.py`.
- Local development auto-disables jobs and message flags to prevent spam (see `disable_features_for_local_env()` in `main.py`).
