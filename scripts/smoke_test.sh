#!/usr/bin/env bash
set -euo pipefail
BASE_URL="${1:?Usage: $0 https://.../dev}"
echo "Health:"
curl -fsS "$BASE_URL/health" && echo
