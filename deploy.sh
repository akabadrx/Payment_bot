#!/bin/bash
# deploy.sh - Safe deployment script that preserves the database

# Stop the old container
docker stop paymentbot 2>/dev/null || true
docker rm paymentbot 2>/dev/null || true

# Build the new image
docker build --no-cache -t paymentbot .

# Create the database file if it doesn't exist (prevents Docker from creating a directory)
touch /root/paymentbot/bot_state.db

# Run with volume mount to preserve database
docker run -d \
  --name paymentbot \
  --restart always \
  --env-file .env \
  -v /root/paymentbot/bot_state.db:/app/bot_state.db \
  paymentbot

echo "✅ Deployment complete! Database preserved."
docker logs -f paymentbot
