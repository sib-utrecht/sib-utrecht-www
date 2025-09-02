#!/bin/sh

# Install a systemd service + timer to run `sib-tools sync all` daily
set -e

SERVICE_USER=$(id -un)
WORKDIR=$(pwd)
SERVICE_FILE=/etc/systemd/system/sib-www-sync.service
TIMER_FILE=/etc/systemd/system/sib-www-sync.timer

echo "Using user: $SERVICE_USER"
echo "Using workdir: $WORKDIR"

mkdir data -p
# mkdir temp -p
# mkdir static -p

# Create service unit (oneshot)
cat <<EOF | sudo tee $SERVICE_FILE > /dev/null
[Unit]
Description=SIB website sync (https://github.com/sib-utrecht/sib-utrecht-www)
After=network.target

[Service]
Type=oneshot
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$WORKDIR
# Ensure venv/bin is preferred if present
Environment=PYTHONUNBUFFERED=1
Environment=PATH=$WORKDIR/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=/bin/sh $WORKDIR/sync_website.sh

# Security settings
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
#ProtectHome=yes
# ReadWritePaths=$WORKDIR/data /home/fedora/edit-sib-utrecht-nl/data/www

[Install]
WantedBy=multi-user.target
EOF

# Create timer unit (daily)
cat <<EOF | sudo tee $TIMER_FILE > /dev/null
[Unit]
Description=SIB website sync timer (https://github.com/sib-utrecht/sib-utrecht-www)

[Timer]
# Run every day at 8:00 in summer time, 7:00 in winter time.
OnCalendar=06:00
# Make up for missed runs if the machine was off
Persistent=false
# Add a small random delay to avoid thundering herd
# RandomizedDelaySec=5m
# RandomizedDelaySec=5m

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable sib-www-sync.timer
sudo systemctl start sib-www-sync.timer

echo "Installed and started sib-www-sync.timer."
echo "Check with: systemctl status sib-www-sync.timer && systemctl list-timers | grep sib-www-sync"
