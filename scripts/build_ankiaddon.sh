#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v zip >/dev/null 2>&1; then
  echo "error: zip not found (install zip first)" >&2
  exit 1
fi

out_dir="${1:-"$repo_root/dist"}"
out_file="${2:-"notify-empty-decks.ankiaddon"}"

mkdir -p "$out_dir"
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

# Minimal addon payload. Include docs for convenience, but do not bundle
# the developer's local config.json (it may contain personal settings).
files=(
  "__init__.py"
  "manifest.json"
  "README.md"
  "DESIGN.md"
)

for f in "${files[@]}"; do
  if [[ -f "$repo_root/$f" ]]; then
    cp "$repo_root/$f" "$tmpdir/"
  fi
done

cat >"$tmpdir/config.json" <<'JSON'
{
  "menu_title": "Find Empty New-Card Decks",
  "show_when_profile_opens": false,
  "notify_every_n_days": 0,
  "notify_never": true,
  "last_opened_at": 0,
  "name_filter": "",
  "filter_filtered_decks": true,
  "filter_container_decks": true,
  "filter_empty_decks": true,
  "filter_limits_zero": true,
  "filter_available_zero": true,
  "filter_has_new": true
}
JSON

out_path="$out_dir/$out_file"
rm -f "$out_path"
(cd "$tmpdir" && zip -qr "$out_path" .)
zip -T "$out_path" >/dev/null
echo "$out_path"

