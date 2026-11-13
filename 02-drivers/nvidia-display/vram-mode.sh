#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Select NVIDIA coherent GPU memory mode on the HP OmniBook X.
#
# This writes the driver module option. It does not change the firmware
# DRAM reservation. Check MemTotal and the kernel Memory: line after reboot.
#
#   bash 02-drivers/nvidia-display/vram-mode.sh
#   sudo bash 02-drivers/nvidia-display/vram-mode.sh dedicated
#   sudo bash 02-drivers/nvidia-display/vram-mode.sh shared
#   sudo bash 02-drivers/nvidia-display/vram-mode.sh shared --reboot
set -euo pipefail

CONF=/etc/modprobe.d/hp-omnibook-vram.conf
PRESET=/etc/mkinitcpio.d/linux-n1x-nvidia-bin.preset

usage() {
  sed -n '3,11p' "$0" | sed 's/^# \{0,1\}//'
}

gib() {
  awk -v kib="$1" 'BEGIN { printf "%.1f", kib / 1024 / 1024 }'
}

active_mode() {
  awk -F'"' '/CoherentGPUMemoryMode/ { print $2; exit }' /proc/driver/nvidia/params 2>/dev/null || true
}

pending_mode() {
  if [[ ! -f "$CONF" ]]; then
    echo "(unset, driver default)"
    return
  fi
  awk -F= '/^options nvidia NVreg_CoherentGPUMemoryMode=/ { print $2; exit }' "$CONF"
}

status() {
  local mem_kib reserved_kib phys_kib mode pending line
  mem_kib=$(awk '/^MemTotal:/ { print $2; exit }' /proc/meminfo)
  mode=$(active_mode)
  pending=$(pending_mode)
  reserved_kib=""
  phys_kib=""
  # awk closes the pipe early, so journalctl dies with SIGPIPE. Keep the line anyway.
  line=$(journalctl -k -b -o cat --no-pager 2>/dev/null | awk '/^Memory: / { print; exit }' || true)
  if [[ -n "$line" ]]; then
    phys_kib=$(printf '%s\n' "$line" | sed -n 's/.*\/\([0-9][0-9]*\)K available.*/\1/p')
    reserved_kib=$(printf '%s\n' "$line" | sed -n 's/.* \([0-9][0-9]*\)K reserved.*/\1/p')
  fi

  echo "Running mode:  ${mode:-unknown}"
  echo "Saved for next boot:  $pending"
  echo "Linux MemTotal:  $(gib "$mem_kib") GiB"
  if [[ -n "$phys_kib" && -n "$reserved_kib" ]]; then
    echo "Firmware picture at boot:  $(gib "$phys_kib") GiB present, $(gib "$reserved_kib") GiB reserved"
  fi
  echo
  echo "dedicated  selects driver-managed coherent GPU memory."
  echo "shared     selects NUMA mode and enables migration."
  echo "Neither command changes the firmware reservation."
  if [[ "${mode:-}" != "numa" && "$pending" == numa ]]; then
    echo
    echo "shared is saved. It is not active until you reboot."
  elif [[ "${mode:-}" != "driver" && "$pending" == driver ]]; then
    echo
    echo "dedicated is saved. It is not active until you reboot."
  fi
}

write_conf() {
  local mode=$1 uvm nvidia_mode
  case "$mode" in
    dedicated) uvm=1 ;;
    shared) uvm=0 ;;
    *) echo "unknown mode: $mode" >&2; exit 2 ;;
  esac
  nvidia_mode=$mode
  [[ "$mode" == dedicated ]] && nvidia_mode=driver
  [[ "$mode" == shared ]] && nvidia_mode=numa

  cat >"$CONF" <<EOF
# Written by vram-mode.sh. Keep this file limited to the two lines below.
# dedicated -> NVreg_CoherentGPUMemoryMode=driver
# shared    -> NVreg_CoherentGPUMemoryMode=numa
options nvidia NVreg_CoherentGPUMemoryMode=${nvidia_mode}
options nvidia-uvm uvm_disable_sam_migration=${uvm}
EOF
  echo "wrote $CONF"
}

rebuild() {
  if [[ ! -f "$PRESET" ]]; then
    echo "missing initramfs preset: $PRESET" >&2
    return 1
  fi
  mkinitcpio -p linux-n1x-nvidia-bin
}

change_mode() (
  local mode=$1 saved had_conf=0 changed=0
  [[ ! -L "$CONF" ]] || { echo "refusing symlink: $CONF" >&2; return 1; }
  saved=$(mktemp "${CONF}.rollback.XXXXXX") || return 1
  if [[ -f "$CONF" ]]; then
    had_conf=1
    cp -a -- "$CONF" "$saved" || { rm -f -- "$saved"; return 1; }
  fi
  cleanup() {
    local result=$?
    trap - EXIT INT TERM
    if (( changed )); then
      if (( had_conf )); then
        if ! cp -a -- "$saved" "$CONF"; then
          echo "Configuration restore failed; recovery copy retained at $saved" >&2
          exit 1
        fi
      else
        rm -f -- "$CONF" || exit 1
      fi
      # A failed build can already have replaced one of its outputs.
      if ! rebuild; then
        echo "Recovery rebuild failed. Keep this session open and use the saved boot/USB recovery path." >&2
        result=1
      fi
    fi
    rm -f -- "$saved"
    exit "$result"
  }
  trap cleanup EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM
  changed=1
  write_conf "$mode" || return 1
  rebuild || return 1
  changed=0
)

main() {
if (( $# > 2 )); then
  usage >&2
  return 2
fi

cmd=${1:-status}
reboot_after=0
if [[ "${2:-}" == "--reboot" ]]; then
  reboot_after=1
elif [[ -n "${2:-}" ]]; then
  echo "unknown option: $2" >&2
  usage >&2
  exit 2
fi

case "$cmd" in
  status|-h|--help|help)
    status
    echo
    echo "Change it with:  sudo bash $0 dedicated"
    echo "                 sudo bash $0 shared"
    ;;
  dedicated|shared)
    if [[ "$(id -u)" -ne 0 ]]; then
      echo "run: sudo bash $0 $cmd" >&2
      exit 1
    fi
    python3 "$(dirname -- "$0")/../../lib/hp_boot.py" guard || return 1
    if ! change_mode "$cmd"; then
      echo "initramfs rebuild failed; the previous configuration was restored." >&2
      return 1
    fi
    echo
    status
    echo
    echo "The desktop is still on the old mode. Reboot to apply $cmd."
    if [[ "$reboot_after" -eq 1 ]]; then
      systemctl reboot
    fi
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
  main "$@"
fi
