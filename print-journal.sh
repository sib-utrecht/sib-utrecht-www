#!/bin/sh

journalctl -fu sib-www-sync --no-hostname -o short | sed -E 's/^([A-Z
][a-z]{2} [ 0-9][0-9] [0-9]{2}:[0-9]{2}:[0-9]{2}) [^:]+: (.*)$/\1 | \2/'

