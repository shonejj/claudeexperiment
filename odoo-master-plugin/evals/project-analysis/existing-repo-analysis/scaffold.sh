#!/usr/bin/env bash
# Copies a fixture repository into the eval workspace (run with --scaffold).
set -euo pipefail
ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../../.." && pwd)}"
cp -r "$ROOT/tests/fixtures/odoo16_legacy/." .
git init -q . && git add -A && git -c user.email=eval@example.com -c user.name=eval commit -qm fixture
