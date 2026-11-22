#!/usr/bin/env bash
# Builds the Splunkbase package dist/<app id>-<version>.tgz from the files git tracks.
# Leaves out tests/, ci/, dotfiles, __pycache__ and *.pyc (Splunkbase file standards).
# Writes dist/package.env (APP, VERSION, PKG) and dist/SHA256SUMS for the later steps.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

conf() {  # conf <stanza> <key>: value from default/app.conf
  awk -v s="[$1]" -v k="$2" '{ sub(/\r$/, "") } $0 == s { f = 1; next } /^\[/ { f = 0 }
    f { split($0, a, / *= */); if (a[1] == k) { print a[2]; exit } }' default/app.conf
}
APP=$(conf package id)
VERSION=$(conf launcher version)
[ -n "$APP" ] && [ -n "$VERSION" ] || { echo "build: app.conf needs [package] id and [launcher] version" >&2; exit 1; }
[ "$(conf id version)" = "$VERSION" ] || { echo "build: [id] version and [launcher] version differ in app.conf" >&2; exit 1; }
if [ -f app.manifest ] && ! grep -q "\"version\": *\"$VERSION\"" app.manifest; then
  echo "build: app.manifest version differs from app.conf ($VERSION)" >&2; exit 1
fi

rm -rf dist
mkdir -p "dist/$APP"
git ls-files -z | grep -zvE '^(tests|ci)/|(^|/)\.|(^|/)__pycache__/|\.py[co]$' | tar --null -T - -cf - | tar -xf - -C "dist/$APP"
find "dist/$APP" -type d -exec chmod 755 {} +
find "dist/$APP" -type f -exec chmod 644 {} +
find "dist/$APP/bin" -maxdepth 1 -type f \( -name '*.py' -o -name '*.sh' \) -exec chmod 755 {} + 2>/dev/null || true

PKG="dist/$APP-$VERSION.tgz"
# Same commit, same bytes: fixed owner, order and timestamps, gzip without a name/time header.
tar --owner=0 --group=0 --numeric-owner --sort=name --mtime="@$(git log -1 --format=%ct)" \
    -C dist -cf - "$APP" | gzip -n -9 > "$PKG"
(cd dist && sha256sum "$(basename "$PKG")" > SHA256SUMS)
printf 'APP=%s\nVERSION=%s\nPKG=%s\n' "$APP" "$VERSION" "$PKG" > dist/package.env
echo "build: $PKG ($(tar -tzf "$PKG" | wc -l) entries) $(cut -c1-16 dist/SHA256SUMS)"
