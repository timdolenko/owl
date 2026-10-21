#!/usr/bin/env bash
# Installs the skill for Claude Code and/or Codex CLI and creates the Python venv the scripts use.
#   ./install.sh [--claude] [--codex] [--copy]     default: both, as symlinks to this checkout
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
HOME_DIR="${REPTILE_HOME:-$HOME/.cache/reptile}"
TARGETS=() MODE=link
for arg in "$@"; do
  case "$arg" in
    --claude) TARGETS+=("$HOME/.claude/skills") ;;
    --codex) TARGETS+=("${CODEX_HOME:-$HOME/.codex}/skills") ;;
    --copy) MODE=copy ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done
[ ${#TARGETS[@]} -eq 0 ] && TARGETS=("$HOME/.claude/skills" "${CODEX_HOME:-$HOME/.codex}/skills")

for dir in "${TARGETS[@]}"; do
  mkdir -p "$dir"
  dest="$dir/reptile"
  if [ -e "$dest" ] || [ -L "$dest" ]; then
    [ "$(cd "$dest" 2>/dev/null && pwd -P)" = "$SRC" ] && { echo "already installed: $dest"; continue; }
    echo "exists, not touched: $dest (remove it to reinstall)" >&2; continue
  fi
  if [ "$MODE" = copy ]; then
    mkdir -p "$dest" && cp -R "$SRC/SKILL.md" "$SRC/scripts" "$SRC/prompts" "$SRC/modes" "$dest/"
  else
    ln -s "$SRC" "$dest"
  fi
  echo "installed: $dest"
done

mkdir -p "$HOME_DIR"
[ -x "$HOME_DIR/venv/bin/python" ] || python3 -m venv "$HOME_DIR/venv"
"$HOME_DIR/venv/bin/pip" install -q --upgrade pip
"$HOME_DIR/venv/bin/pip" install -q -r "$SRC/requirements.txt"
echo "venv: $HOME_DIR/venv"
