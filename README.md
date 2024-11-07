# Rides Coordinator Bot

This is a Discord bot that puts out an announcement for users who need a ride for some event.

## Commands
- `/ask-drivers [message]` - Pings `@Drivers` for who is available. `[message]` field is for custom message after the `@Driver` ping.

## Installing
Clone the repository and `cd` into the folder:
```
$ git clone https://github.com/brentonmdunn/rides-coordinator-bot
$ cd rides-coordinator-bot
```

(optional) Create virtual environment:
```
$ python3 -m venv .venv
$ source .venv/bin/activate
```

Install dependencies:
```
$ pip install -r requirements.txt
```

Add environment variables:
```
Create .env file
Add TOKEN=<Discord token>
Add BOT_NAME=<bot name>
Add GUILD_ID=<guild ID>
DRIVERS_CHANNEL=<channel ID to send drivers message>
```

### Building Docker Image 
```
$ docker buildx create --use --name multi-platform-builder --driver docker-container
$ docker buildx build --platform linux/amd64,linux/arm64 -t brentonmdunn/ride-bot --push .
```