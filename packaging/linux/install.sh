#!/usr/bin/env bash
set -euo pipefail

# Port redirect: TCP :80  -> :13131 (IPv4)
FROM_PORT=80
TO_PORT=13131

# ---------- helpers ----------
need_root() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "ERROR: Run as root (or: sudo $0)" >&2
    exit 1
  fi
}

has_cmd() { command -v "$1" >/dev/null 2>&1; }

rule_exists() {
  # args: <table> <chain> <rule...>
  local table="$1"; shift
  local chain="$1"; shift
  iptables -t "$table" -C "$chain" "$@" >/dev/null 2>&1
}

add_rule_if_missing() {
  # args: <table> <chain> <rule...>
  local table="$1"; shift
  local chain="$1"; shift
  if rule_exists "$table" "$chain" "$@"; then
    echo "OK: rule already present: iptables -t $table -A $chain $*"
  else
    echo "ADD: iptables -t $table -A $chain $*"
    iptables -t "$table" -A "$chain" "$@"
  fi
}

detect_os() {
  # outputs: ubuntu|debian|arch|unknown
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

backup_file() {
  local f="$1"
  if [[ -f "$f" ]]; then
    local ts
    ts="$(date +%Y%m%d_%H%M%S)"
    cp -a "$f" "${f}.bak.${ts}"
    echo "BACKUP: $f -> ${f}.bak.${ts}"
  fi
}

install_ubuntu_persistence() {
  echo "Installing persistence packages (Ubuntu/Debian)..."
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y

  # Avoid interactive iptables-persistent prompts
  if has_cmd debconf-set-selections; then
    echo "iptables-persistent iptables-persistent/autosave_v4 boolean true" | debconf-set-selections || true
    echo "iptables-persistent iptables-persistent/autosave_v6 boolean true" | debconf-set-selections || true
  fi

  apt-get install -y iptables iptables-persistent netfilter-persistent

  # Ensure service is enabled
  systemctl enable --now netfilter-persistent >/dev/null 2>&1 || true
}

save_ubuntu_rules() {
  echo "Saving rules (Ubuntu/Debian)..."
  # netfilter-persistent save writes /etc/iptables/rules.v4
  netfilter-persistent save
}

install_arch_persistence() {
  echo "Installing persistence packages (Arch)..."
  pacman -Sy --noconfirm --needed iptables
}

save_arch_rules() {
  echo "Saving rules (Arch)..."
  mkdir -p /etc/iptables
  backup_file /etc/iptables/iptables.rules
  iptables-save > /etc/iptables/iptables.rules
  systemctl enable --now iptables
}

# ---------- main ----------
need_root

OS_FAMILY="$(detect_os)"
echo "Detected OS family: $OS_FAMILY"

if ! has_cmd iptables; then
  case "$OS_FAMILY" in
    ubuntu|debian) install_ubuntu_persistence ;;
    arch)         install_arch_persistence ;;
    *)            echo "ERROR: Unsupported OS (no /etc/os-release match). Install iptables manually." >&2; exit 2 ;;
  esac
fi

# Add redirect rules:
# - PREROUTING: handles inbound traffic from the network
# - OUTPUT: handles local traffic originating on the same machine (e.g. curl http://localhost)
add_rule_if_missing nat PREROUTING -p tcp --dport "$FROM_PORT" -j REDIRECT --to-ports "$TO_PORT"
add_rule_if_missing nat OUTPUT     -p tcp -o lo --dport "$FROM_PORT" -j REDIRECT --to-ports "$TO_PORT"

echo "Current NAT table rules (filtered):"
iptables -t nat -S | sed -n 's/^/- /p' | grep -E "PREROUTING|OUTPUT|REDIRECT|--dport ${FROM_PORT}|to-ports ${TO_PORT}" || true

# Persist rules per distro
case "$OS_FAMILY" in
  ubuntu|debian)
    # If packages weren't installed earlier, ensure they're present now
    if ! has_cmd netfilter-persistent; then
      install_ubuntu_persistence
    fi
    save_ubuntu_rules
    ;;
  arch)
    save_arch_rules
    ;;
  *)
    echo "WARNING: Unknown OS family; persistence not configured." >&2
    ;;
esac

echo "DONE: Redirecting TCP :${FROM_PORT} -> :${TO_PORT} (IPv4), with persistence configured."
echo
echo "To undo (manual):"
echo "  sudo iptables -t nat -D PREROUTING -p tcp --dport ${FROM_PORT} -j REDIRECT --to-ports ${TO_PORT}"
echo "  sudo iptables -t nat -D OUTPUT -p tcp -o lo --dport ${FROM_PORT} -j REDIRECT --to-ports ${TO_PORT}"
echo "  # then re-save persistence (netfilter-persistent save OR iptables-save > /etc/iptables/iptables.rules)"

