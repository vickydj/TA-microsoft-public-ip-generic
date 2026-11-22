#!/usr/bin/env bash
# Splunk AppInspect (Splunkbase + Splunk Cloud checks) and the Packaging Toolkit (SLIM) on the package
# from ci/build.sh. Fails on any AppInspect failure or error, or any SLIM error.
# Needs: pip install -r ci/requirements.txt (Linux or macOS; AppInspect needs libmagic).
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
. dist/package.env

splunk-appinspect inspect "$PKG" --mode precert --included-tags cloud --included-tags splunk_appinspect \
  --data-format json --output-file dist/appinspect.json > dist/appinspect.log 2>&1 || true
# AppInspect exits 3 for passing and failing apps alike, so read the summary instead.
python3 - dist/appinspect.json <<'EOF'
import json, sys
report = json.load(open(sys.argv[1]))["reports"][0]
s = report["summary"]
print("appinspect:", {k: s[k] for k in ("failure", "error", "future_failure", "warning", "success")})
for group in report["groups"]:
    for check in group["checks"]:
        if check["result"] in ("failure", "error"):
            msg = (check["messages"] or [{}])[0].get("message", "")
            print(f"::error::AppInspect {check['result']}: {check['name']}: {msg[:300]}")
sys.exit(1 if s["failure"] + s["error"] else 0)
EOF

slim validate "$PKG"
echo "check: AppInspect and SLIM passed for $PKG"
