#!/usr/bin/env bash
set -euo pipefail

# Undo script for the port redirect + persistence changes created by the install script.
# Removes:
#   - iptables NAT REDIRECT rules for TCP :80 -> :13131
#   - persistence config created/used by:
#       * Ubuntu/Debian: netfilter-persistent / iptables-persistent
#       * Arch: /etc/iptables/iptables.rules + iptables service enablement
#
# Behavior:
#   - Safe to run multiple times (it will only delete what exists).
#   - It will DISABLE persistence services and may REMOVE packages on Ubuntu/Debian.
#   - On Arch it does NOT uninstall iptables (common dependency), but disables service and clears saved rules file.

FROM_PORT=80
TO_PORT=13131

need_root() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "ERROR: Run as root (or: sudo $0)" >&2
    exit 1
  fi
}

has_cmd() { command -v "$1" >/dev/null 2>&1; }

detect_os() {
  if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    local id="${ID:-}"
    local like="${ID_LIKE:-}"
    if [[ "$id" == "ubuntu" ]]; then echo "ubuntu"; return; fi
    if [[ "$id" == "debian" || "$like" == *"debian"* ]]; then echo "debian"; return; fi
    if [[ "$id" == "arch" || "$like" == *"arch"* ]]; then echo "arch"; return; fi
  fi
  echo "unknown"
}

rule_exists() {
  local table="$1"; shift
  local chain="$1"; shift
  iptables -t "$table" -C "$chain" "$@" >/dev/null 2>&1
}

delete_rule_if_present() {
  local table="$1"; shift
  local chain="$1"; shift
  if rule_exists "$table" "$chain" "$@"; then
    echo "DEL: iptables -t $table -D $chain $*"
    iptables -t "$table" -D "$chain" "$@"
  else
    echo "OK: rule not present: iptables -t $table -D $chain $*"
  fi
}

backup_file() {
  local f="$1"
  if [[ -f "$f" ]]; then
    local ts
    ts="$(date +%Y%m%d_%H%M%S)"
    cp -a "$f" "${f}.bak.${ts}"
    echo "BACKUP: $f -> ${f}.bak.${ts}"
  fi
}

disable_service_if_exists() {
  local svc="$1"
  if has_cmd systemctl; then
    if systemctl list-unit-files | grep -qE "^${svc}\.service"; then
      systemctl disable --now "$svc" >/dev/null 2>&1 || true
      echo "SERVICE: disabled/stopped $svc"
    fi
  fi
}

ubuntu_remove_persistence_packages() {
  # This removes packages that were typically installed for persistence.
  # If you prefer to keep them, comment out the apt-get purge line.
  if has_cmd apt-get; then
    echo "Ubuntu/Debian: disabling netfilter-persistent and purging persistence packages..."
    disable_service_if_exists netfilter-persistent

    # Purge persistence packages; keep iptables itself.
    apt-get purge -y iptables-persistent netfilter-persistent || true
    apt-get autoremove -y || true
  fi
}

ubuntu_resave_empty_rules_if_possible() {
  # If netfilter-persistent still exists (user chose not to purge), save current rule state.
  if has_cmd netfilter-persistent; then
    echo "Ubuntu/Debian: saving current rules (after deletions)..."
    netfilter-persistent save || true
  fi
}

arch_disable_persistence() {
  echo "Arch: disabling iptables persistence service and clearing saved rules file..."
  disable_service_if_exists iptables

  if [[ -f /etc/iptables/iptables.rules ]]; then
    backup_file /etc/iptables/iptables.rules
    rm -f /etc/iptables/iptables.rules
    echo "FILE: removed /etc/iptables/iptables.rules"
  else
    echo "OK: /etc/iptables/iptables.rules not present"
  fi
}

# ---------- main ----------
need_root

OS_FAMILY="$(detect_os)"
echo "Detected OS family: $OS_FAMILY"

if ! has_cmd iptables; then
  echo "NOTE: iptables not found; cannot remove rules. Exiting." >&2
  exit 0
fi

# Remove the same rules the install script added:
# - PREROUTING: inbound traffic
# - OUTPUT: local traffic (lo)
delete_rule_if_present nat PREROUTING -p tcp --dport "$FROM_PORT" -j REDIRECT --to-ports "$TO_PORT"
delete_rule_if_present nat OUTPUT     -p tcp -o lo --dport "$FROM_PORT" -j REDIRECT --to-ports "$TO_PORT"

echo "Remaining NAT table rules (filtered):"
iptables -t nat -S | sed -n 's/^/- /p' | grep -E "PREROUTING|OUTPUT|REDIRECT|--dport ${FROM_PORT}|to-ports ${TO_PORT}" || true

case "$OS_FAMILY" in
  ubuntu|debian)
    # If you want to KEEP persistence packages, comment out the purge function call
    # and keep only the resave function.
    ubuntu_remove_persistence_packages
    ubuntu_resave_empty_rules_if_possible
    ;;
  arch)
    arch_disable_persistence
    ;;
  *)
    echo "WARNING: Unknown OS family; persistence cleanup not performed." >&2
    ;;
esac

echo "DONE: Removed redirect TCP :${FROM_PORT} -> :${TO_PORT} and cleaned persistence where applicable."

