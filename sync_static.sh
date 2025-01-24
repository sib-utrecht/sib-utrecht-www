#!/bin/sh
set -e

find static/ -maxdepth 50 -type f -name "*.time" -delete
find static/ -maxdepth 50 -type f -name "*.query" -delete

rclone config create sib-utrecht s3 provider=AWS region=eu-central-1 location_constraint=eu-central-1 storage_class=INTELLIGENT_TIERING env_auth=true
rclone sync static \
    sib-utrecht:sib-utrecht-www1/sib-utrecht-www/live --checksum -v


