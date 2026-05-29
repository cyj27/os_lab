#!/usr/bin/env bash

set -euo pipefail

real_docker="${REAL_DOCKER:-$(command -v docker || true)}"
user_name="${USER:-$(id -un)}"
script_dir="$(cd -- "$(dirname -- "$0")" && pwd)"

if [[ -z "${real_docker}" ]]; then
	echo "[docker-wrapper] docker command not found." >&2
	exit 127
fi

can_run_docker() {
	"$real_docker" info >/dev/null 2>&1
}

run_with_sg() {
	if ! command -v sg >/dev/null 2>&1; then
		return 1
	fi

	local quoted
	printf -v quoted '%q ' "$real_docker" "$@"
	sg docker -c "$quoted"
}

run_with_sudo() {
	if ! command -v sudo >/dev/null 2>&1; then
		return 1
	fi
	if ! sudo -n "$real_docker" info >/dev/null 2>&1; then
		return 1
	fi
	sudo "$real_docker" "$@"
}

in_docker_group_db() {
	getent group docker 2>/dev/null | awk -F: -v user="$user_name" '
		{
			n = split($4, members, ",");
			for (i = 1; i <= n; ++i) {
				if (members[i] == user) {
					found = 1;
				}
			}
		}
		END { exit found ? 0 : 1 }'
}

print_helpful_error() {
	local sock_group=""
	local sock_mode=""

	if [[ -S /var/run/docker.sock ]]; then
		sock_group="$(stat -c '%G' /var/run/docker.sock 2>/dev/null || true)"
		sock_mode="$(stat -c '%A' /var/run/docker.sock 2>/dev/null || true)"
	fi

	echo "[docker-wrapper] docker is installed, but this shell cannot talk to the daemon." >&2
	if [[ -n "$sock_group" ]]; then
		echo "[docker-wrapper] /var/run/docker.sock group=${sock_group} mode=${sock_mode}" >&2
	fi
	if in_docker_group_db && ! id -nG | tr ' ' '\n' | grep -qx docker; then
		echo "[docker-wrapper] You are already listed in the docker group, but this shell has not picked it up yet." >&2
		echo "[docker-wrapper] Try: newgrp docker" >&2
	fi
	if [[ "${sock_group}" != "" && "${sock_group}" != "docker" ]]; then
		echo "[docker-wrapper] The docker socket group is not 'docker'; this is usually a daemon/socket setup issue." >&2
		echo "[docker-wrapper] One-time fix: sudo bash ${script_dir}/fix-docker.sh" >&2
	fi
	echo "[docker-wrapper] If docker was just installed, also make sure the daemon is running:" >&2
	echo "[docker-wrapper]   sudo systemctl enable --now docker docker.socket" >&2
	exit 1
}

if can_run_docker; then
	exec "$real_docker" "$@"
fi

if in_docker_group_db && run_with_sg info >/dev/null 2>&1; then
	exec sg docker -c "$(printf '%q ' "$real_docker" "$@")"
fi

if run_with_sudo "$@"; then
	exit 0
fi

print_helpful_error
