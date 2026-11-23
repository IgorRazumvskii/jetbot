#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."
exec python3 demo/server.py "${1:-results/replay-first-segment}"
