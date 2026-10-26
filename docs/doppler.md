# Production secrets with Doppler

The Docker images support Doppler at startup. When `DOPPLER_TOKEN_FILE` or
`DOPPLER_TOKEN` is supplied, secrets are loaded before database backup, migrations,
and application startup. Without either setting, the existing environment-based
startup continues to work.

## Prepare Doppler

Import the existing production environment into the production config. Preserve
variable names and values; use `backend/.env.example` as a reference. In particular:

- `APP_ENV=prod`
- `RIDEBOT_TOKEN` (not `DISCORD_BOT_TOKEN`)
- The existing `DATABASE_URL`, pointing into the container's `/app/db` mount
- `REDIS_URL=redis://redis:6379`
- Existing authentication settings and `INTERNAL_API_SECRET`

Do not replace the database URL with an example value. Keep Slack forwarding
credentials enabled in only one environment. Create a read-only service token
scoped to the production config.

## Deploy

First build and publish the updated image through the repository's normal PR
workflow. The old published image does not include Doppler support.

On the production server, place `deploy/docker-compose.doppler.yaml` alongside
your current Compose file, in the same deployment directory. Keep the same Compose
project name so existing named volumes (including Redis) are reused. Run all the
following commands from that directory.

Save the token without putting it in shell history. This explicitly invokes Bash
and also works when your interactive shell is zsh:

```bash
bash -c '
umask 077
read -r -s -p "Paste your Doppler token: " token || exit 1
printf "\n"
[ -n "$token" ] || { echo "No token entered; file unchanged."; exit 1; }
printf "%s" "$token" > .doppler-token
chmod 600 .doppler-token
echo "Token saved."
'
test -s .doppler-token && echo "Token file is nonempty"
```

Keep the existing `.env` as a rollback option. The new Compose file does not load
it. Verify that `./db` contains the current production database and retain a
database backup before switching.

```bash
docker compose -f docker-compose.doppler.yaml config --quiet
docker compose -f docker-compose.doppler.yaml pull
docker compose -f docker-compose.doppler.yaml up -d
docker compose -f docker-compose.doppler.yaml ps
docker compose -f docker-compose.doppler.yaml logs --tail=100 ride-bot
curl --fail http://localhost:8000/health
```

Use the same `-p PROJECT_NAME` option on every command if the existing deployment
uses an explicit project name. Check logs before sharing them; avoid commands that
print secrets. This Compose file is standalone, not an override to merge with the
old file.

Once the updated `update.sh` and `docker-compose.doppler.yaml` are copied to the
VM deployment directory, `bash update.sh` automatically selects Doppler when
`.doppler-token` exists. An empty token file stops the update. The script pulls
the published image; it does not run `git pull` or copy deployment files from
this repository. Keep the same Compose project name as before (set
`COMPOSE_PROJECT_NAME` if needed).

## Updates and recovery

After editing secrets, restart the application to fetch them:

```bash
docker compose -f docker-compose.doppler.yaml restart ride-bot
```

The `doppler-cache` volume stores an encrypted fallback, allowing startup during a
Doppler outage after a successful fetch. First startup requires Doppler access.
The fallback uses the service token to derive its encryption key. Rotate tokens
while Doppler is reachable so a new snapshot can be saved. Cached credentials can
remain usable after token revocation; delete the cached snapshot when deliberately
revoking offline access. Do not run `down -v`: it also deletes persistent volumes.

To roll back, restore your original image and Compose configuration with the
original `.env`, using the same project name and database mounts.

References: [Doppler Docker setup](https://docs.doppler.com/docs/dockerfile),
[encrypted fallbacks](https://docs.doppler.com/docs/automatic-fallbacks).
