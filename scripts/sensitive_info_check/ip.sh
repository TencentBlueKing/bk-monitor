#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Files passed by pre-commit (relative to repo root). If none, nothing to check.
if [[ "$#" -eq 0 ]]; then
  exit 0
fi

CHANGE_FILES=("$@")

# Default allowlists:
# - ip_white_list.dat: allowlisted IPs or grep patterns
# - ip_white_list_paths.dat: allowlisted files/paths (e.g. lock files may contain dotted versions like 2.9.21.202)
# - ip_white_list.local.dat: optional per-developer local allowlist (not required to exist)
WHITELIST_FILES=(
  "$BASE_DIR/ip_white_list.dat"
)
for f in "$BASE_DIR/ip_white_list_paths.dat" "$BASE_DIR/ip_white_list.local.dat"; do
  [[ -f "$f" ]] && WHITELIST_FILES+=("$f")
done

# Optional extra allowlist files (colon-separated). Example:
#   export BK_IP_WHITELIST_FILES="scripts/sensitive_info_check/ip_white_list.local.dat:/abs/path/to/allowlist.dat"
if [[ -n "${BK_IP_WHITELIST_FILES:-}" ]]; then
  IFS=":" read -r -a extra_files <<< "${BK_IP_WHITELIST_FILES}"
  for ef in "${extra_files[@]}"; do
    [[ -z "$ef" ]] && continue
    WHITELIST_FILES+=("$ef")
  done
fi

TMP_ALLOWLIST="$(mktemp)"
cleanup() { rm -f "$TMP_ALLOWLIST"; }
trap cleanup EXIT

for wf in "${WHITELIST_FILES[@]}"; do
  [[ -f "$wf" ]] || continue
  # Drop comments/blank lines to avoid accidental "match all" patterns.
  grep -vE '^\s*($|#)' "$wf" >> "$TMP_ALLOWLIST" || true
done

# Match IPv4-looking strings, and print "file:line:match".
IP_REGEX='(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)'

matches="$(grep -aEinoH "$IP_REGEX" -- "${CHANGE_FILES[@]}" || true)"
if [[ -n "$matches" && -s "$TMP_ALLOWLIST" ]]; then
  matches="$(printf '%s\n' "$matches" | grep -v -f "$TMP_ALLOWLIST" || true)"
fi

if [[ -z "${matches}" ]]; then
  exit 0
fi

while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  echo "invalid:${line}"
done <<< "$matches"

exit 1