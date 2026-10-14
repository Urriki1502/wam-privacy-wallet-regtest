#!/usr/bin/env bash
# Creates a completely new public MIT GitHub repo under the intended owner.
set -euo pipefail
cd "$(dirname "$0")/.."
command -v git >/dev/null || { echo 'git is required' >&2; exit 2; }
command -v gh >/dev/null || { echo 'Install GitHub CLI: brew install gh' >&2; exit 2; }
if ! gh auth status >/dev/null 2>&1; then
  echo 'Sign in first: gh auth login' >&2
  exit 2
fi
owner="$(gh api user --jq .login)"
if [ "$owner" != "Urriki1502" ]; then
  echo 'GitHub login is not Urriki1502; refusing to create repo in a different account.' >&2
  exit 2
fi
if [ ! -d .git ]; then git init -b main; fi
if git remote get-url origin >/dev/null 2>&1; then
  echo 'origin remote already exists; refusing to change it.' >&2
  exit 2
fi
git add .
git commit -m 'chore: initialize real WAM Core REGTEST-first macOS wallet'
gh repo create Urriki1502/wam-privacy-wallet-regtest --public --source=. --remote=origin --push \
  --description 'WAM Core v0.1.11 real REGTEST wallet, macOS ARM64 first'
echo 'New independent public MIT repository pushed: https://github.com/Urriki1502/wam-privacy-wallet-regtest'
