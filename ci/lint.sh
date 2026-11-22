#!/usr/bin/env bash
# Fast checks for what this repo has shipped before and AppInspect does not flag.
# Used by the pre-push hook (ci/hooks/pre-push), validate.yml and release.yml.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

# ---- repo settings -------------------------------------------------------------
LIBS=(':!bin/ta_microsoft_public_ip_generic/aob_py3')  # vendored libraries, skipped by the secret and TLS checks
ALLOW_EXPOSE=1            # the Add-on Builder/UCC configuration UI calls its handlers through web.conf
# ---------------------------------------------------------------------------------

fail=0
err() { echo "::error::$1"; fail=1; }

if git ls-files | grep -E '(^|/)local/|^metadata/local\.meta$|\.backup$|(^|/)__pycache__/|\.py[co]$'; then
  err "Instance state or bytecode is committed (local/, local.meta, *.backup, __pycache__, *.pyc)"; fi
if git grep -nE 'eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.|\$7\$[A-Za-z0-9+/=]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----' -- . "${LIBS[@]}"; then
  err "A token, encrypted secret or private key is committed"; fi
if git grep -niE '^\s*requireAuthentication\s*=\s*(false|0|f|no)\s*$' -- '*restmap.conf'; then
  err "A REST endpoint does not require authentication"; fi
if [ "$ALLOW_EXPOSE" != 1 ] && git grep -n '^\[expose:' -- '*web.conf'; then
  err "web.conf exposes a REST endpoint through Splunk Web"; fi
if git grep -nE 'verify\s*=\s*False|CERT_NONE|_create_unverified_context' -- 'bin/*.py' "${LIBS[@]}"; then
  err "TLS verification is disabled in Python code"; fi

[ "$fail" = 0 ] && echo "lint: ok"
exit "$fail"
