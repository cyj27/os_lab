#!/usr/bin/env bash

set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
	echo "Run this script with sudo: sudo bash $0" >&2
	exit 1
fi

target_user="${SUDO_USER:-${USER:-}}"

if ! command -v systemctl >/dev/null 2>&1; then
	echo "systemctl not found; cannot repair docker daemon/socket automatically." >&2
	exit 1
fi

if ! getent group docker >/dev/null 2>&1; then
	groupadd docker
fi

if [[ -n "${target_user}" ]] && id -u "${target_user}" >/dev/null 2>&1; then
	usermod -aG docker "${target_user}" || true
fi

mkdir -p /etc/systemd/system/docker.socket.d
cat >/etc/systemd/system/docker.socket.d/override.conf <<'EOF'
[Socket]
SocketGroup=docker
SocketMode=0660
ListenStream=
ListenStream=/run/docker.sock
EOF

systemctl daemon-reload
systemctl enable docker.service docker.socket
systemctl restart docker.socket docker.service

if [[ -S /var/run/docker.sock ]]; then
	chgrp docker /var/run/docker.sock || true
	chmod 660 /var/run/docker.sock || true
fi

echo "[fix-docker] docker service restarted."
echo "[fix-docker] Open a new shell or run: newgrp docker"
