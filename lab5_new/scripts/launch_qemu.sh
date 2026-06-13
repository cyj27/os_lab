#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/launch_qemu.sh --iso <iso-file> --disk <disk-file> --ssh-port <port>

Options:
  --iso PATH       SystemRescue ISO
  --disk PATH      repair-fs lab disk, raw or qcow2
  --format FMT     disk format, default inferred from file suffix
  --memory SIZE    QEMU memory size, default 4G
  --cpus N         QEMU CPU count, default 2
  --ssh-port PORT  host localhost port forwarded to SystemRescue port 22
USAGE
}

iso=""
disk=""
format=""
memory="4G"
cpus="2"
ssh_port=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --iso)
      iso="${2:-}"
      shift 2
      ;;
    --disk)
      disk="${2:-}"
      shift 2
      ;;
    --format)
      format="${2:-}"
      shift 2
      ;;
    --memory)
      memory="${2:-}"
      shift 2
      ;;
    --cpus)
      cpus="${2:-}"
      shift 2
      ;;
    --ssh-port)
      ssh_port="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$iso" || -z "$disk" ]]; then
  usage >&2
  exit 2
fi

if [[ ! -f "$iso" ]]; then
  echo "error: ISO not found: $iso" >&2
  exit 1
fi

if [[ ! -f "$disk" ]]; then
  echo "error: disk not found: $disk" >&2
  exit 1
fi

if [[ -z "$format" ]]; then
  case "$disk" in
    *.raw) format="raw" ;;
    *) format="qcow2" ;;
  esac
fi

if [[ -z "$ssh_port" ]]; then
  echo "error: ssh port not specified" >&2
  exit 1
fi

exec qemu-system-x86_64 \
  -m "$memory" \
  -smp "$cpus" \
  -boot d \
  -cdrom "$iso" \
  -drive "file=$disk,if=virtio,format=$format,cache=writeback" \
  -device virtio-rng-pci \
  -nographic \
  -netdev user,id=net0,hostfwd=tcp:127.0.0.1:${ssh_port}-:22 -device virtio-net-pci,netdev=net0
