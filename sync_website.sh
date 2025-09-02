#!/bin/sh

set -e
cd data/
python ../cache.py

cd ../
./sync_static_server.sh
