#!/bin/sh

rclone sync data/static /home/fedora/edit-sib-utrecht-nl/data/www/html -v --checksum
