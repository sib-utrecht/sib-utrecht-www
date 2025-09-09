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
# ListenStream=/run/sib-www-journal.sock
# # World-readable socket so container can proxy after bind-mount; tighten if you manage shared groups
# SocketMode=0666
# Listen on loopback TCP; container should proxy to host via host.docker.internal
ListenStream=127.0.0.1:9099
Accept=yes

[Install]
WantedBy=sockets.target
EOF

# Create service template that prints last 100 journal lines over HTTP
cat <<EOF | sudo tee $JOURNAL_SERVICE_FILE > /dev/null
[Unit]
Description=SIB WWW journal endpoint (per-connection service)
After=systemd-journald.service

[Service]
Type=simple
StandardInput=socket
StandardOutput=socket
StandardError=journal
User=fedora
Group=fedora
# Minimal, read-only FS hardening
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict

# Return HTTP headers and the journal output in the desired format
# ExecStart=/bin/sh -c '/usr/bin/printf "HTTP/1.1 200 OK\r\nContent-Type: text/plain; charset=utf-8\r\nCache-Control: no-store\r\n\r\n"; /usr/bin/journalctl -u sib-www-sync --no-hostname -o short -n 100 | /usr/bin/sed -E "s/^([A-Z][a-z]{2} [ 0-9][0-9] [0-9]{2}:[0-9]{2}:[0-9]{2}) [^:]+: (.*)$/\\1 | \\2/"'
# ExecStart=/bin/sh -c '/usr/bin/printf "HTTP/1.1 200 OK\r\nContent-Type: text/plain; charset=utf-8\r\nCache-Control: no-store\r\n\r\nHello!\r\n";'

# Read and discard request headers, then respond
# ExecStart=/bin/sh -c '/usr/bin/logger -t sib-www-journal "connection"; /usr/bin/sed -u "/^\r\?$/q" >/dev/null; /usr/bin/printf "HTTP/1.1 200 OK\r\nContent-Type: text/plain; charset=utf-8\r\nCache-Control: no-store\r\n\r\nHello!\r\n";'
ExecStart=/bin/sh -c '/usr/bin/logger -t sib-www-journal "connection"; /usr/bin/sed -u "/^\r\?$/q" >/dev/null; /usr/bin/printf "HTTP/1.1 200 OK\r\nContent-Type: text/plain; charset=utf-8\r\nCache-Control: no-store\r\n\r\nLatest 100 lines of log:\r\n"; /usr/bin/journalctl -u sib-www-sync --no-hostname -o short -n 100 | /usr/bin/sed -E "s/^([A-Z][a-z]{2} [ 0-9][0-9] [0-9]{2}:[0-9]{2}:[0-9]{2}) [^:]+: (.*)$/\\1 | \\2/"'

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
