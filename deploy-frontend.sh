#!/bin/bash
# Deploy frontend build to backend admin_ui directory

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Deploying frontend to backend...${NC}"

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
BACKEND_DIR="$SCRIPT_DIR/backend"
DIST_DIR="$FRONTEND_DIR/dist"
ADMIN_UI_DIR="$BACKEND_DIR/admin_ui"

# Check if dist exists
if [ ! -d "$DIST_DIR" ]; then
    echo "❌ Error: dist directory not found. Run 'npm run build' first."
    exit 1
fi

# Create admin_ui directory if it doesn't exist
mkdir -p "$ADMIN_UI_DIR"

# Remove old files (but keep .gitkeep if it exists)
echo -e "${BLUE}🧹 Cleaning old files...${NC}"
GITKEEP_TMP="$SCRIPT_DIR/.gitkeep.tmp"

if [ -f "$ADMIN_UI_DIR/.gitkeep" ]; then
    mv "$ADMIN_UI_DIR/.gitkeep" "$GITKEEP_TMP"
fi
rm -rf "$ADMIN_UI_DIR"/*
if [ -f "$GITKEEP_TMP" ]; then
    mv "$GITKEEP_TMP" "$ADMIN_UI_DIR/.gitkeep"
fi

# Copy new files
echo -e "${BLUE}📦 Copying build files...${NC}"
cp -r "$DIST_DIR"/* "$ADMIN_UI_DIR"/

echo -e "${GREEN}✅ Frontend deployed successfully to backend/admin_ui/${NC}"
echo -e "${GREEN}Files copied: $(ls -1 $ADMIN_UI_DIR | wc -l | xargs)${NC}"
