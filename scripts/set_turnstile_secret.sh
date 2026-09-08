#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <turnstile-secret-arn-or-name> <turnstile-secret>" >&2
  exit 1
fi
aws secretsmanager put-secret-value \
  --secret-id "$1" \
  --secret-string "{\"secret\":\"$2\"}"
