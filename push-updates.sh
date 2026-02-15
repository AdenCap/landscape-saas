#!/usr/bin/env bash
# Push all updates to GitHub: add everything, commit, and push.
# Usage: ./push-updates.sh [optional commit message]
# If no message is given, uses "Update: <date>"

set -e
cd "$(dirname "$0")"

MSG="${*:-Update: $(date '+%Y-%m-%d %H:%M')}"
git add -A

if git diff --staged --quiet 2>/dev/null; then
  echo "Nothing to commit (working tree clean)."
  if git log origin/main..HEAD --oneline 2>/dev/null | head -1 | grep -q .; then
    echo "Pushing existing commits..."
    git push origin main
  else
    echo "Nothing to push."
  fi
  exit 0
fi

git commit -m "$MSG"
git push origin main
echo "Done. Pushed to GitHub."
