#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/akgularda/RadioTEDU}"
TARGET_DIR="${TARGET_DIR:-$PWD/RadioTEDU}"

if [ -d "$TARGET_DIR/.git" ]; then
  cd "$TARGET_DIR"
  git pull --ff-only
else
  git clone "$REPO_URL" "$TARGET_DIR"
  cd "$TARGET_DIR"
fi

if [ ! -f ".env" ] && [ -f ".env.example" ]; then
  cp ".env.example" ".env"
fi

echo
echo "RadioTEDU website server starter is ready."
echo "Open this prompt in Codex and execute it:"
echo "$(pwd)/handoff/web-server/prompt.md"
echo
cat "handoff/web-server/prompt.md"
