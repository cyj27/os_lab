#!/usr/bin/env bash

set -euo pipefail
script_dir="$(cd -- "$(dirname -- "$0")" && pwd)"

echo "[doctor] Host checks"

check_cmd() {
	if command -v "$1" >/dev/null 2>&1; then
		echo "[ok] $1: $(command -v "$1")"
	else
		echo "[miss] $1"
	fi
}

check_cmd docker
check_cmd qemu-system-aarch64
check_cmd aarch64-linux-gnu-gcc
check_cmd python3
check_cmd make

if command -v docker >/dev/null 2>&1; then
	if "$script_dir/docker.sh" info >/dev/null 2>&1; then
		echo "[ok] docker daemon reachable"
	else
		echo "[warn] docker installed but this shell still cannot reach the daemon"
	fi
fi

if [[ -S /var/run/docker.sock ]]; then
	echo "[doctor] docker.sock: $(stat -c '%A %U %G %n' /var/run/docker.sock)"
	if [[ "$(stat -c '%G' /var/run/docker.sock)" != "docker" ]]; then
		echo "[warn] docker.sock group is not 'docker'; run: sudo bash $script_dir/fix-docker.sh"
	fi
fi

if getent group docker >/dev/null 2>&1; then
	echo "[doctor] docker group: $(getent group docker)"
	if getent group docker | awk -F: -v user="${USER:-$(id -un)}" '
		{
			n = split($4, members, ",");
			for (i = 1; i <= n; ++i) {
				if (members[i] == user) {
					found = 1;
				}
			}
		}
		END { exit found ? 0 : 1 }'; then
		if ! id -nG | tr ' ' '\n' | grep -qx docker; then
			echo "[warn] your account is in the docker group, but this shell has not picked it up yet; run: newgrp docker"
		fi
	fi
fi

if test -e /dev/kvm; then
	echo "[ok] /dev/kvm present"
else
	echo "[warn] /dev/kvm absent: QEMU will run with TCG only and official grading may be slow"
fi

if grep -qi microsoft /proc/version 2>/dev/null; then
	echo "[warn] WSL detected: full-system QEMU is usually slower here than on native Linux"
fi

echo "[doctor] Recommended commands"
echo "  Quick local check: make local-grade"
echo "  Official local grading: make official-grade-local TIMEOUT=600"
echo "  Docker grading (if installed): make grade"
