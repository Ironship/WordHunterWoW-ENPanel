# Running a subagent on OpenAI Codex instead of a Claude model

## What is and isn't possible

Claude Code's `model:` field in an agent definition accepts Anthropic models
only — `haiku`, `sonnet`, `opus`, `inherit`. There is no setting that points a
subagent at an OpenAI model. A subagent is a loop inside Claude Code talking to
the Anthropic API.

What works instead: a subagent that shells out to the locally installed Codex
CLI. Claude Code still runs the loop, but the reasoning happens in Codex. That
is what `.claude/agents/codex.md` does. The wrapper agent is pinned to `haiku`
on purpose — it only runs one command and relays the output, so there is no
reason to pay for a larger model to hold the pipe.

## Setup

1. Install and sign in to the Codex CLI on the machine where Claude Code runs:

   ```
   npm install -g @openai/codex
   codex login
   ```

   Signing in with a ChatGPT account uses that plan's quota; an API key is
   billed per token instead.

2. Confirm non-interactive mode works and check which flags your build has:

   ```
   codex exec --help
   codex exec "reply with the word ok"
   ```

3. Pick the model. `codex-run.sh` passes `CODEX_SUBAGENT_MODEL` to `codex -m`.
   Leave it unset to use whatever the local Codex config already defaults to.
   List what your account actually offers with `codex --help` or by checking
   `~/.codex/config.toml`, and set the id from that list — an id that does not
   exist is rejected at call time.

   ```
   export CODEX_SUBAGENT_MODEL=<model-id-from-your-account>
   ```

4. Use it from Claude Code:

   ```
   > ask the codex subagent to review Tools/build_quest_lua.py for edge cases
   ```

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `CODEX_SUBAGENT_MODEL` | Codex CLI default | Model id passed to `codex -m` |
| `CODEX_SUBAGENT_SANDBOX` | `read-only` | `read-only`, `workspace-write`, or `danger-full-access` |
| `CODEX_SUBAGENT_CD` | repo root | Directory Codex treats as its workspace |

Read-only is the default so a delegated question cannot quietly rewrite the
working tree. Raise it to `workspace-write` only for a task where Codex is
meant to edit files.

To make this agent available in every project rather than this one, copy
`.claude/agents/codex.md` and `.claude/scripts/codex-run.sh` to `~/.claude/`
and change the script path in the agent body to an absolute one.

## The other route: Codex as an MCP server

`codex mcp` exposes Codex over MCP, which you can register with
`claude mcp add codex -- codex mcp`. That gives the main Claude session a Codex
*tool* it can call, rather than a subagent with its own context window. Use the
subagent when you want the delegated task isolated in its own context; use MCP
when you want Claude to consult Codex inline mid-task.
