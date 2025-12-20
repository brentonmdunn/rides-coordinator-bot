#!/bin/bash

# Prompt for migration message
read -p "📝 Enter a migration name: " MIGRATION_MSG

# Ensure Alembic is available
if ! command -v alembic &> /dev/null; then
  echo "❌ Alembic is not installed. Run: pip install alembic"
  exit 1
fi

# Step 1: Generate migration
echo "📦 Generating migration..."
alembic revision --autogenerate -m "$MIGRATION_MSG"

# Step 2: Show recent migration file
LATEST=$(ls alembic/versions/ | sort | tail -n 1)
echo "✅ Created migration: alembic/versions/$LATEST"

# Step 3: Ask to apply it
read -p "⚙️  Apply migration now? [y/N]: " APPLY

if [[ "$APPLY" == "y" || "$APPLY" == "Y" ]]; then
  alembic upgrade head
  echo "🚀 Migration applied."
else
  echo "📎 Migration saved but not applied."
fi
