#!/bin/bash

# Job Finder Bot - Docker Run Script

echo "🚀 Starting Job Finder Bot..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ .env file not found! Please create one with your Telegram credentials."
    exit 1
fi

# Build the Docker image
echo "🔨 Building Docker image..."
docker build -t jobfinder-bot .

# Run the container
echo "🏃 Running Job Finder Bot..."
docker run --rm \
    --env-file .env \
    -v "$(pwd)/seen_jobs.db:/app/seen_jobs.db" \
    --name jobfinder-bot \
    jobfinder-bot

echo "✅ Job Finder Bot stopped."
