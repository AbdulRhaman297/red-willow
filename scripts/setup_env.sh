#!/usr/bin/env bash
# Interactive helper to create a local .env file without echoing secrets
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${SCRIPT_DIR}/.."
ENV_FILE="${ROOT}/.env"

echo "This script will add the required API keys to ${ENV_FILE} (it will create the file if missing)."
read -sp "SHODAN_API_KEY: " SHODAN
echo
read -sp "IPINFO_TOKEN: " IPINFO
echo
read -sp "OPENWEATHER_API_KEY: " OPENWEATHER
echo

# Write values (overwrite existing keys in file safely)
# Create .env if doesn't exist
touch "$ENV_FILE"

# helper to set or replace a key in .env
set_key() {
  local key="$1" value="$2" file="$3"
  if grep -qE "^${key}=" "$file"; then
    # replace existing line
    sed -i"" -e "s#^${key}=.*#${key}=${value}#" "$file" 2>/dev/null || sed -i -e "s#^${key}=.*#${key}=${value}#" "$file"
  else
    echo "${key}=${value}" >> "$file"
  fi
}

set_key "SHODAN_API_KEY" "$SHODAN" "$ENV_FILE"
set_key "IPINFO_TOKEN" "$IPINFO" "$ENV_FILE"
set_key "OPENWEATHER_API_KEY" "$OPENWEATHER" "$ENV_FILE"

# Ensure .env is ignored by git
if [ -f "${ROOT}/.gitignore" ] && ! grep -q "^\.env$" "${ROOT}/.gitignore"; then
  echo ".env" >> "${ROOT}/.gitignore"
  echo "Added .env to .gitignore"
fi

echo "Wrote keys to ${ENV_FILE}. To load them now: set -a && source .env && set +a"
exit 0
