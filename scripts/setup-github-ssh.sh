#!/usr/bin/env bash
# One-time setup: create an SSH key for GitHub and show instructions.
# Run: ./scripts/setup-github-ssh.sh

set -e
KEY="$HOME/.ssh/id_ed25519_github"
CONFIG="$HOME/.ssh/config"
GITHUB_URL="https://github.com/settings/ssh/new?title=MacBook&target=AdenCap"

echo "=== GitHub SSH setup ==="
echo ""

if [[ -f "$KEY.pub" ]]; then
  echo "Key already exists: $KEY.pub"
else
  echo "Creating new SSH key at $KEY"
  ssh-keygen -t ed25519 -C "github" -f "$KEY" -N "" || true
  echo "Key created."
fi

if [[ -f "$KEY" ]]; then
  eval "$(ssh-agent -s)" 2>/dev/null || true
  ssh-add "$KEY" 2>/dev/null || true

  if ! grep -q "Host github.com" "$CONFIG" 2>/dev/null; then
    echo ""
    echo "Adding GitHub entry to ~/.ssh/config"
    mkdir -p "$(dirname "$CONFIG")"
    {
      echo ""
      echo "Host github.com"
      echo "  HostName github.com"
      echo "  User git"
      echo "  IdentityFile $KEY"
    } >> "$CONFIG"
    echo "Done."
  fi

  echo ""
  echo "--- NEXT STEP: Add this key to GitHub ---"
  echo "1. Your public key (copied to clipboard if possible):"
  echo ""
  cat "$KEY.pub"
  echo ""
  if command -v pbcopy >/dev/null 2>&1; then
    pbcopy < "$KEY.pub"
    echo "   (Already copied to clipboard.)"
  fi
  echo "2. Open: $GITHUB_URL"
  echo "3. Paste the key and click 'Add SSH key'."
  echo "4. Then run: ssh -T git@github.com"
  echo "5. Then push: git push origin main"
  echo ""
  if command -v open >/dev/null 2>&1; then
    read -p "Open GitHub SSH settings in browser now? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      open "$GITHUB_URL"
    fi
  fi
else
  echo "Could not create key. Run manually:"
  echo "  ssh-keygen -t ed25519 -C 'your_email@example.com' -f $KEY"
fi
