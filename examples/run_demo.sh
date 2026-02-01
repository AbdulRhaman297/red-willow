#!/usr/bin/env bash
# Simple demo script for red-willow (non-interactive)
# Usage: ./examples/run_demo.sh "weather London"

set -euo pipefail
cmd=${1:-"weather London"}
python -m main --command "$cmd" --no-audio
