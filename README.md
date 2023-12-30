# Rides Coordinator Bot

This is a Discord bot that puts out an announcement for users who need a ride for some event. Users who react to the message will automatically be paired with a driver. The pairings use flow network graph algorithms and takes into number of cars, deviation from standard route without pickups, and where groups of people need to be picked up.

Commands:
```
/send - sends ride message
/group - groups users by location
```

Admin commands: (can only be run by certain users)
```
/admin_get_rxn_users - Gets all user info or a named user (optional param).
/admin_list_user_info - Gets list of users who reacted to message.
/admin_help - Slash commands available for admins.
```

**Branch protection is turned on. Any change must be made though a PR.**

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
```
