#!/run/current-system/sw/bin/bash

rm dev2.sib-utrecht.nl/wp-login* 2>/dev/null
rm dev2.sib-utrecht.nl/index.html?p=* 2>/dev/null
rm -r dev2.sib-utrecht.nl/author 2>/dev/null

aws-vault exec vincent-laptop2-nixos-sib --no-session -- rclone sync dev2.sib-utrecht.nl \
    sib-aws:sib-utrecht-www1/sib-utrecht-www/live --checksum -v
