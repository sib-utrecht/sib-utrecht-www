#!/bin/sh

set -e

find ./static -maxdepth 20 -type f -name "*.css" -delete
find ./static -maxdepth 20 -type f -name "*.html" -delete
find ./static -maxdepth 20 -type f -name "*.js" -delete

python cache.py

git add .
git commit -m "Regenerate all html and css files"
git push

