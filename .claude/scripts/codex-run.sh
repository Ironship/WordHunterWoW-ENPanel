#!/usr/bin/env bash
# Run a prompt through the local Codex CLI and print the result on stdout.
#
# Used by the `codex` subagent (.claude/agents/codex.md) so that delegated work
# runs on an OpenAI model instead of a Claude one.
#
# Usage:  codex-run.sh "prompt text"
#         echo "prompt text" | codex-run.sh
#
# Environment:
#   CODEX_SUBAGENT_MODEL    model passed to `codex -m`. Unset = whatever the
#                           local Codex config already defaults to.
#   CODEX_SUBAGENT_SANDBOX  read-only (default) | workspace-write | danger-full-access
#   CODEX_SUBAGENT_CD       working directory for Codex. Default: repo root.

set -euo pipefail

if ! command -v codex >/dev/null 2>&1; then
  echo "codex-run.sh: the 'codex' CLI is not on PATH." >&2
  echo "Install it (npm i -g @openai/codex, or the ChatGPT desktop app's CLI) and sign in with 'codex login'." >&2
  exit 127
fi

prompt="${1-}"
if [ -z "$prompt" ]; then
  prompt="$(cat)"
fi
if [ -z "${prompt//[[:space:]]/}" ]; then
  echo "codex-run.sh: empty prompt." >&2
  exit 2
fi

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

args=(exec)
[ -n "${CODEX_SUBAGENT_MODEL-}" ] && args+=(-m "$CODEX_SUBAGENT_MODEL")
args+=(--sandbox "${CODEX_SUBAGENT_SANDBOX:-read-only}")
args+=(--cd "${CODEX_SUBAGENT_CD:-$repo_root}")
args+=(--skip-git-repo-check)
args+=("$prompt")

exec codex "${args[@]}"
