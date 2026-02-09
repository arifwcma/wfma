#!/usr/bin/env bash
#
# diagnosis.sh - fast compromise triage (Ubuntu on EC2)
# Writes report to /tmp/out.txt (and also echoes to terminal if tee exists).
#
# NOTE:
# - This script is intentionally READ-ONLY (no removals/changes).
# - It avoids printing private key material. SSH key output is fingerprints only.
#
set -u
set -o pipefail

OUT="/tmp/out.txt"

if command -v tee >/dev/null 2>&1; then
  exec > >(tee "$OUT") 2>&1
else
  exec >"$OUT" 2>&1
fi

section() {
  printf "\n\n===== %s =====\n" "$1"
}

run() {
  # Run a command, but keep going on errors.
  local cmd="$*"
  echo
  echo "+ $cmd"
  ( set +e; bash -lc "$cmd"; echo "exit_code=$?" )
}

section "META"
run "date -u"
run "uname -a"
run "uptime"
run "id"
run "who"
run "last -a | head -n 50"

section "AUTH LOG (HIGH SIGNAL)"
run "sudo awk '/Accepted publickey/{a++} /Accepted password/{b++} /Failed password/{c++} /Invalid user/{d++} END{print \"Accepted_pubkey=\"a,\"Accepted_pass=\"b,\"Failed_pass=\"c,\"Invalid_user=\"d}' /var/log/auth.log 2>/dev/null || true"
run "sudo grep -E \"Accepted|Failed password|Invalid user|authentication failure\" /var/log/auth.log | tail -n 200 2>/dev/null || true"
run "sudo lastb -a | head -n 50 2>/dev/null || echo \"no btmp/lastb data\""
run "sudo grep -E \"sudo:\" /var/log/auth.log | tail -n 160 2>/dev/null || true"

section "USERS / SSH KEYS (FINGERPRINTS ONLY)"
run "awk -F: '\$3==0{print}' /etc/passwd"
run "sudo ls -la /root/.ssh 2>/dev/null || true"
run "ls -la ~/.ssh 2>/dev/null || true"
run "for f in /home/*/.ssh/authorized_keys /root/.ssh/authorized_keys; do [ -f \"\$f\" ] && echo \"--- \$f\" && sudo ssh-keygen -lf \"\$f\" 2>/dev/null; done"

section "NETWORK LISTENERS / PROCESSES"
run "sudo ss -tulpn"
run "ps auxfww --sort=-%cpu | head -n 40"
run "ps auxfww --sort=-%mem | head -n 40"

section "PERSISTENCE (CRON / SYSTEMD)"
run "crontab -l 2>/dev/null || true"
run "sudo crontab -l 2>/dev/null || true"
run "sudo ls -la /etc/cron* /etc/cron.* 2>/dev/null || true"
run "systemctl --no-pager list-timers --all | head -n 220"
run "systemctl --no-pager list-unit-files --state=enabled | head -n 260"

section "SUSPICIOUS FILES (CRON / UDEV)"
run "sudo ls -la /etc/cron.d/auto-upgrade /etc/udev/rules.d/99-auto-upgrade.rules /etc/crontab /etc/cron.d 2>/dev/null || true"
run "sudo sha256sum /etc/cron.d/auto-upgrade /etc/udev/rules.d/99-auto-upgrade.rules 2>/dev/null || true"
run "sudo find /etc/cron* /etc/udev/rules.d -type f -perm -0002 -ls 2>/dev/null | head -n 200"

# Show cron payload safely (truncate)
run "if [ -f /etc/cron.d/auto-upgrade ]; then echo '--- /etc/cron.d/auto-upgrade (first 300 chars)'; sudo head -c 300 /etc/cron.d/auto-upgrade; echo; echo '--- (last 300 chars)'; sudo tail -c 300 /etc/cron.d/auto-upgrade; echo; fi"

# Show udev rule file (usually short)
run "sudo sed -n '1,200p' /etc/udev/rules.d/99-auto-upgrade.rules 2>/dev/null || true"

# Decode any embedded base64 safely (no execution)
run "if [ -f /etc/cron.d/auto-upgrade ]; then sudo awk '{print \$7}' /etc/cron.d/auto-upgrade 2>/dev/null | head -n 1 | base64 -d 2>/dev/null | sed -n '1,200p' || true; fi"

section "KERNEL / SYSTEM WARNINGS (THIS BOOT)"
run "dmesg -T | tail -n 200"
run "sudo journalctl -p warning..alert -b --no-pager | tail -n 220"

section "FIREWALL"
run "sudo ufw status verbose 2>/dev/null || true"

section "PACKAGE ACTIVITY"
run "sudo tail -n 200 /var/log/apt/history.log 2>/dev/null || true"

section "DOCKER (IF PRESENT)"
run "command -v docker >/dev/null 2>&1 && sudo docker ps --no-trunc || echo 'docker not present or no permission'"

section "DONE"
echo "Wrote report to: $OUT"
