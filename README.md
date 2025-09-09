# Job Finder Bot

A Python bot that monitors RemoteOK for new job postings matching your keywords and sends notifications via Telegram.

## Features

- 🔍 Monitors RemoteOK for new job postings
- 🎯 Keyword matching based on your skills
- 📱 Telegram notifications for new matches
- 💾 SQLite database to track seen jobs
- 🐳 Docker support for easy deployment
- ⏰ Configurable polling intervals

## Quick Start

### 1. Set up APIs

#### Telegram Bot Setup:
1. **Create a bot:**
   - Message `@BotFather` on Telegram
   - Send `/newbot`
   - Choose a name and username for your bot
   - Save the token you receive

2. **Get your Chat ID:**
   - Start a chat with your new bot
   - Send any message
   - Visit: `https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates`
   - Find your chat ID in the response

#### JSearch API Setup:
1. **Get API Key:**
   - Visit [RapidAPI JSearch](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch)
   - Sign up for a free account
   - Subscribe to the JSearch API (free tier available)
   - Copy your API key

#### Active Jobs API Setup:
1. **Get API Key:**
   - Visit [RapidAPI Active Jobs](https://rapidapi.com/active-jobs-db/api/active-jobs-db)
   - Sign up for a free account
   - Subscribe to the Active Jobs API (free tier available)
   - Copy your API key

#### LinkedIn Jobs API Setup:
1. **Get API Key:**
   - Visit [RapidAPI LinkedIn Jobs](https://rapidapi.com/linkedin-job-search-api/api/linkedin-job-search-api)
   - Sign up for a free account
   - Subscribe to the LinkedIn Jobs API (free tier available)
   - Copy your API key

#### Glassdoor API Setup:
1. **Get API Key:**
   - Visit [RapidAPI Glassdoor](https://rapidapi.com/glassdoor-real-time/api/glassdoor-real-time)
   - Sign up for a free account
   - Subscribe to the Glassdoor API (free tier available)
   - Copy your API key

#### Indeed API Setup:
1. **Get API Key:**
   - Visit [RapidAPI Indeed](https://rapidapi.com/indeed12/api/indeed12)
   - Sign up for a free account
   - Subscribe to the Indeed API (free tier available)
   - Copy your API key

2. **Update your `.env` file:**
   ```bash
   TELEGRAM_TOKEN=your_bot_token_here
   TELEGRAM_CHAT_ID=your_chat_id_here
   JSEARCH_API_KEY=your_jsearch_api_key_here
   ACTIVE_JOBS_API_KEY=your_active_jobs_api_key_here
   LINKEDIN_JOBS_API_KEY=your_linkedin_jobs_api_key_here
   GLASSDOOR_API_KEY=your_glassdoor_api_key_here
   INDEED_API_KEY=your_indeed_api_key_here
   ```

### 2. Test Telegram Connection

```bash
# Install dependencies locally (optional, for testing)
pip install -r requirements.txt

# Test your Telegram setup
python test_telegram.py
```

### 3. Run with Docker

```bash
# Make the run script executable (already done)
chmod +x run.sh

# Run the bot
./run.sh
```

Or manually with Docker:

```bash
# Build the image
docker build -t jobfinder-bot .

# Run the container
docker run --rm \
    --env-file .env \
    -v "$(pwd)/seen_jobs.db:/app/seen_jobs.db" \
    --name jobfinder-bot \
    jobfinder-bot
```

## Configuration

Edit your `.env` file to customize the bot:

```bash
# Required
TELEGRAM_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
JSEARCH_API_KEY=your_jsearch_api_key
ACTIVE_JOBS_API_KEY=your_active_jobs_api_key
LINKEDIN_JOBS_API_KEY=your_linkedin_jobs_api_key
GLASSDOOR_API_KEY=your_glassdoor_api_key
INDEED_API_KEY=your_indeed_api_key

# Optional
POLL_SECONDS=120          # How often to check (default: 2 minutes)
COUNTRY=us               # Country code for job search
REMOTE_ONLY=1            # Only remote jobs (1=yes, 0=no)
MAX_YEARS_EXP=5          # Maximum years of experience
DB_PATH=seen_jobs.db     # Database file path
```

## Keywords

The bot searches for jobs containing these keywords (edit in `main.py`):

- Full stack development
- Frontend/Backend technologies
- React, TypeScript, Next.js
- C#, .NET, Blazor, ASP.NET
- PostgreSQL, Supabase
- AWS, Python, C++
- tRPC, Prisma

## How It Works

1. **Polling**: Bot checks RemoteOK every 2 minutes (configurable)
2. **Filtering**: Only shows jobs posted in the last hour
3. **Matching**: Searches job titles, descriptions, and tags for your keywords
4. **Deduplication**: Tracks seen jobs in SQLite database
5. **Notifications**: Sends formatted messages to Telegram

## Troubleshooting

### Bot not sending messages
- Verify your `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID` in `.env`
- Run `python test_telegram.py` to test connection
- Make sure you've started a chat with your bot

### No jobs found
- Check if RemoteOK is accessible
- Verify your keywords in `main.py`
- Check the logs for error messages

### Docker issues
- Ensure Docker is running
- Check that your `.env` file exists
- Verify the database volume mount is working

## Development

To run locally without Docker:

```bash
# Install dependencies
pip install -r requirements.txt

# Run the bot
python main.py
```

## Database

The bot uses SQLite to track seen jobs. The database file (`seen_jobs.db`) is created automatically and persists between runs when using Docker volumes.

## Stopping the Bot

- **Docker**: Press `Ctrl+C` or run `docker stop jobfinder-bot`
- **Local**: Press `Ctrl+C`

## Support

If you encounter issues:
1. Check the logs for error messages
2. Verify your `.env` configuration
3. Test Telegram connection with `test_telegram.py`
4. Ensure RemoteOK is accessible
