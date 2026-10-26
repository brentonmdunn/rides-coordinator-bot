#!/bin/sh
set -eu

# A mounted secret avoids putting the token in Compose or Docker environment metadata.
if [ -n "${DOPPLER_TOKEN_FILE:-}" ]; then
    if [ ! -r "$DOPPLER_TOKEN_FILE" ]; then
        echo "ERROR: Doppler token file is not readable." >&2
        exit 1
    fi
    DOPPLER_TOKEN=$(cat "$DOPPLER_TOKEN_FILE")
    export DOPPLER_TOKEN
    if [ -z "$DOPPLER_TOKEN" ]; then
        echo "ERROR: Doppler token file is empty." >&2
        exit 1
    fi
fi

if [ -n "${DOPPLER_TOKEN:-}" ]; then
    umask 077
    export DOPPLER_CONFIG_DIR="${DOPPLER_CONFIG_DIR:-/var/lib/doppler}"
    mkdir -p "$DOPPLER_CONFIG_DIR"
    exec doppler run --fallback="$DOPPLER_CONFIG_DIR/secrets.encrypted.json" -- /entrypoint.sh "$@"
fi

# Existing deployments can continue to supply their environment directly.
exec /entrypoint.sh "$@"
