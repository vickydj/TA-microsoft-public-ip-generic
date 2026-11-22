#!/usr/bin/env bash
# Prints the README section for the version in dist/package.env (a heading such as "### 1.1.0"),
# for the GitHub release. Falls back to a pointer to the README.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
. dist/package.env
readme=$(ls README.md readme.md 2>/dev/null | head -1)
notes=$(awk -v v="$VERSION" '{ sub(/\r$/, "") }
  /^#+ / { if (f) exit; n = split($0, w, " "); if (w[n] == v) { f = 1; next } }
  f' "${readme:-/dev/null}" 2>/dev/null || true)
if [ -n "$(echo "$notes" | tr -d '[:space:]')" ]; then
  echo "$notes"
else
  echo "See the release notes in the README."
fi
printf '\n---\nPackage: `%s`, SHA-256 `%s`. AppInspect report attached.\n' "$(basename "$PKG")" "$(cut -d' ' -f1 dist/SHA256SUMS)"
