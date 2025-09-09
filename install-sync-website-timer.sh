#!/bin/sh

# Install a systemd service + timer to run `sib-tools sync all` daily
set -e

SERVICE_USER=$(id -un)
WORKDIR=$(pwd)
SERVICE_FILE=/etc/systemd/system/sib-www-sync.service
TIMER_FILE=/etc/systemd/system/sib-www-sync.timer
PATH_FILE=/etc/systemd/system/sib-www-sync.path
JOURNAL_SOCKET_FILE=/etc/systemd/system/sib-www-journal.socket
JOURNAL_SERVICE_FILE=/etc/systemd/system/sib-www-journal@.service

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
# Prevent overlapping runs with an advisory lock
ExecStart=/usr/bin/flock -w 60 $WORKDIR/data/sib-www-sync.lock /bin/sh $WORKDIR/sync_website.sh

# Security settings
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
#ProtectHome=yes
# ReadWritePaths=$WORKDIR/data /home/fedora/edit-sib-utrecht-nl/data/www

[Install]
WantedBy=multi-user.target
EOF

# Create path unit (trigger on Nginx log modification)
cat <<EOF | sudo tee $PATH_FILE > /dev/null
[Unit]
Description=SIB website sync path trigger (watch Nginx trigger log)

[Path]
PathModified=/home/fedora/edit-sib-utrecht-nl/data/nginx/log/trigger_build_access.log
Unit=sib-www-sync.service

[Install]
WantedBy=paths.target
EOF

# Create socket unit for journal endpoint
cat <<EOF | sudo tee $JOURNAL_SOCKET_FILE > /dev/null
[Unit]
Description=SIB WWW journal endpoint (socket-activated)

[Socket]
# Listen on specific addresses; CIDR masks are not supported in ListenStream
# Use the docker bridge IP (adjust if different) and loopback
# ListenStream=172.17.0.1:9099
# ListenStream=127.0.0.1:9099
ListenStream=0.0.0.0:9099
Accept=yes

[Install]
WantedBy=sockets.target
EOF

# Create service template that streams journal as Server-Sent Events (SSE)
cat <<'EOF' | sudo tee $JOURNAL_SERVICE_FILE > /dev/null
[Unit]
Description=SIB WWW journal endpoint (per-connection service)
After=systemd-journald.service

[Service]
Type=oneshot
StandardInput=socket
StandardOutput=socket
StandardError=journal
User=fedora
Group=fedora
# Treat broken pipe / disconnect as success to avoid noisy failures
SuccessExitStatus=141 SIGPIPE

ExecStart=/bin/sh -c '/home/fedora/sib-utrecht-www/stream-log.sh'

Restart=no

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

# No SELinux relabel needed for TCP listener

sudo systemctl daemon-reload
sudo systemctl enable sib-www-sync.timer sib-www-sync.path sib-www-journal.socket
sudo systemctl restart sib-www-sync.timer sib-www-sync.path sib-www-journal.socket

echo "Installed and started sib-www-sync.timer, sib-www-sync.path and sib-www-journal.socket."
echo "Check with: systemctl status sib-www-sync.{service,path,timer} && systemctl status sib-www-journal.socket && systemctl list-timers | grep sib-www-sync && systemctl list-sockets | grep sib-www-journal"
