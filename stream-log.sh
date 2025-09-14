#!/bin/sh

# Be resilient to disconnects: don't exit on pipeline errors
set -e
set -o pipefail
# Ignore SIGPIPE so writes to a closed socket don't terminate with 141
trap '' PIPE

# This script provides a HTTP Server-Sent Events stream (SSE). The
# contents are the logs of the website build script.
#
# A service defined in `install-sync-website-timer.sh` will use this
# script to provide an HTTP endpoint. This endpoint is then routed via
# Nginx to https://edit.sib-utrecht.nl/build-log
# This location will then be loaded by the page
# https://edit.sib-utrecht.nl/update-site/
# in order to display the output logs.

/usr/bin/logger -t sib-www-journal "connection";
# Drain request headers until blank line (handles CRLF or LF)
sed -u "/^\r\?$/q" >/dev/null;
# Send SSE headers
printf "HTTP/1.1 200 OK\r\n";
printf "Content-Type: text/event-stream\r\n";
printf "Cache-Control: no-store\r\n";
printf "Connection: keep-alive\r\n\r\n";
# Optional heartbeat to keep proxies alive
( while :; do sleep 30; printf ": ping\r\n\r\n"; done ) &
# Stream last lines and follow, format, then emit as SSE data events
# If the client disconnects, the printf writes will get SIGPIPE; we ignore it and exit 0

# for some reaons, this sed commands breaks if it is split over multiple lines
{
  journalctl -u sib-www-sync --no-hostname -o short -n 500 -f \
    | sed -uE "/sib-www-sync.service/d;/DEV/d;s/^([A-Z][a-z]{2} [ 0-9][0-9] [0-9]{2}:[0-9]{2}:[0-9]{2}) [^:]+: (.*)$/\1 | \2/" \
    | while IFS= read -r line; do printf "data: %s\r\n\r\n" "$line" || break; done
} || true

# Exit successfully regardless of stream termination reason
exit 0
