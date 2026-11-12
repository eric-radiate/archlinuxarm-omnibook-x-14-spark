#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Install the Wi-Fi regulatory database. Does not select a country.
#
#   sudo bash 03-system/policy/install-wireless-regdb.sh
#
# Then set WIRELESS_REGDOM in /etc/conf.d/wireless-regdom to the country
# where this laptop is used, and reboot or reload the domain.
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "run: sudo bash $0" >&2
  exit 1
fi

pacman -S --needed --noconfirm wireless-regdb iw
echo
echo 'Installed regulatory database:'
pacman -Ql wireless-regdb | grep 'regulatory.db' || true
echo
if command -v iw >/dev/null 2>&1; then
  iw reg get || true
fi
echo
echo 'Set WIRELESS_REGDOM in /etc/conf.d/wireless-regdom to your country.'
echo 'This script does not write a country code.'
