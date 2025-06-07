# Rides Coordinator Bot

This is a Discord bot that helps coordinate ride pickups.


## Installing
Clone the repository and `cd` into the folder:
```
$ git clone https://github.com/brentonmdunn/rides-coordinator-bot
$ cd rides-coordinator-bot
```

(optional) Create virtual environment:
```
$ python -m venv .venv
$ source .venv/bin/activate
```

Install dependencies:
```
$ pip install -r requirements.txt
```

Add environment variables:

Make a copy of `.env.example`, remove the `.example` from the end, and populate the environment variables.

## CI Pipeline
- On each pull request, GitHub actions runs `ruff format --check .` and `ruff check .` and blocks the PR if the code is not properly formatted or linted. Note: it does not autoformat, this must be done on a separate commit.
- On each push or merge to main, GitHub actions builds the Docker image and pushes it to DockerHub. 

Manually build Docker image:
```
$ docker buildx create --use --name multi-platform-builder --driver docker-container
$ docker buildx build --platform linux/amd64,linux/arm64 -t brentonmdunn/ride-bot --push .
```

## Deploying to Synology NAS via Container Manager

- Pull the Docker image from [here](https://hub.docker.com/r/brentonmdunn/ride-bot)
- Enable auto restart
- Map the volumn `/volume1/docker/lscc-discord-bot` to `/app/data:rw`
- Load environment variables
