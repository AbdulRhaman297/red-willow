#!/usr/bin/env bash
# Check presence of required API environment variables (does not print values)
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && cd .. && pwd)"

vars=(SHODAN_API_KEY IPINFO_TOKEN OPENWEATHER_API_KEY)
missing=0
for v in "${vars[@]}"; do
  if [ -z "${!v-}" ]; then
    echo "$v: MISSING"
    missing=1
  else
    echo "$v: SET"
  fi
done

if [ "$missing" -ne 0 ]; then
  echo
  echo "Some required variables are missing. You can run 'bash scripts/setup_env.sh' to add them interactively, or edit .env directly."
  exit 1
else
  echo
  echo "All required API keys appear to be set."
fi
