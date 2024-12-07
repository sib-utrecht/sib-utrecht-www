#!/run/current-system/sw/bin/bash

#aws-vault exec --duration=24h vincent-laptop2-nixos-sib -- code .
aws-vault exec vincent-laptop2-nixos-sib --no-session -- code .

