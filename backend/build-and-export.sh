#!/bin/bash
# Build Docker image for linux/amd64 and export as tar file

set -e  # Exit on error

# Colors for output
#!/bin/bash
set -e

GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; NC='\033[0m'

# Default Dockerfile (can be overridden on the command line)
DOCKERFILE="${1:-Dockerfile}"

IMAGE_NAME="ridebot-website-preprod"
TAR_FILE="${IMAGE_NAME}-amd64.tar"

echo -e "${BLUE}🐳 Building with ${DOCKERFILE}…${NC}"
docker buildx build \
  --platform linux/amd64 \
  -f "${DOCKERFILE}" \
  -t "${IMAGE_NAME}" \
  --load .

echo -e "${BLUE}💾 Exporting Docker image to tar file...${NC}"
docker save $IMAGE_NAME > $TAR_FILE

echo -e "${GREEN}✅ Build complete!${NC}"
echo -e "${GREEN}📦 Image exported to: ${YELLOW}${TAR_FILE}${NC}"
echo -e "${GREEN}📊 File size: $(du -h $TAR_FILE | cut -f1)${NC}"
