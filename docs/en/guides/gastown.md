# Gas Town Integration

[Gas Town](https://github.com/steveyegge/gastown) is a multi-agent orchestration system that coordinates teams of AI agents working on shared codebases. This guide explains how to run Kimi Code CLI as a first-class Gas Town agent using the `kimigas` adapter.

## Overview

Gas Town organizes work through **rigs** (project containers), **crew** (persistent workers), **polecats** (ephemeral task workers), and a **mayor** that coordinates everything. Agents communicate through tmux sessions, and Gas Town dispatches work via `gt sling`.

Kimi Code CLI integrates with Gas Town through three interfaces:

| Interface | Mode | Use case |
|-----------|------|----------|
| Interactive (`--yolo`) | Shell UI in tmux | Crew members, dogs, persistent workers |
| Wire (`--wire`) | JSON-RPC 2.0 via stdin/stdout | Programmatic control, custom orchestrators |
| Print (`--print --input-format stream-json`) | Streaming JSON via stdin/stdout | Polecats, CI/CD, batch work |

## Prerequisites

- [Gas Town](https://github.com/steveyegge/gastown) installed and configured (`gt` CLI available)
- Kimi Code CLI installed (`kimi --version`)
- Kimi Code CLI authenticated (`kimi login` or API key configured)

## Quick start

### 1. Install the kimigas adapter

The `kimigas` adapter is a shell wrapper that bridges Gas Town's agent interface with Kimi Code CLI. Place it on your `PATH`:

```sh
#!/usr/bin/env bash
# ~/bin/kimigas - Kimi Code CLI adapter for Gas Town
set -euo pipefail

KIMI_BIN="${KIMI_BIN:-kimi}"
KIMI_ARGS=()
PASSTHROUGH_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --yolo|--yes|-y|--auto-approve)
            KIMI_ARGS+=("--yolo"); shift ;;
        --wire)
            KIMI_ARGS+=("--wire"); shift ;;
        --print)
            KIMI_ARGS+=("--print"); shift ;;
        -p|--prompt|-c|--command)
            KIMI_ARGS+=("-p" "$2"); shift 2 ;;
        -w|--work-dir)
            KIMI_ARGS+=("--work-dir" "$2"); shift 2 ;;
        --version|-V)
            echo "kimigas (kimi-cli adapter for Gas Town)"
            "$KIMI_BIN" --version 2>/dev/null || true
            exit 0 ;;
        *)
            PASSTHROUGH_ARGS+=("$1"); shift ;;
    esac
done

# Validate kimi is available
if ! command -v "$KIMI_BIN" &>/dev/null; then
    echo "Error: kimi-cli not found. Install with: uv tool install kimi-cli" >&2
    exit 1
fi

# Gas Town compatibility: if CLAUDE.md exists but AGENTS.md doesn't,
# create a symlink so kimi can read the project instructions.
if [[ -n "${GT_ROLE:-}" && -f "CLAUDE.md" && ! -f "AGENTS.md" ]]; then
    ln -sf CLAUDE.md AGENTS.md 2>/dev/null || true
fi

exec "$KIMI_BIN" "${KIMI_ARGS[@]}" "${PASSTHROUGH_ARGS[@]}"
```

Make it executable:

```sh
chmod +x ~/bin/kimigas
```

### 2. Register with Gas Town

Register `kimigas` as a Gas Town agent:

```sh
cd ~/gt
gt config agent set kimigas "kimigas --yolo"
```

Verify registration:

```sh
gt config agent list
# Should show: kimigas [custom] kimigas --yolo
```

### 3. Create a rig

Add your project as a Gas Town rig:

```sh
cd ~/gt
gt rig add myproject https://github.com/org/repo.git --prefix mp
```

### 4. Add crew and start working

```sh
gt crew add koder --rig myproject
gt crew start myproject koder --agent kimigas
```

This launches Kimi Code CLI in an interactive tmux session with `--yolo` mode (auto-approve all actions), ready to receive work.

## Communication modes

### Interactive mode (crew workers)

Interactive mode is the primary way to run Kimi Code CLI as a Gas Town crew member. Kimi starts its full shell UI inside a tmux session, with `--yolo` enabled so it can execute tools without manual approval.

```sh
# Gas Town starts this automatically via gt crew start --agent kimigas
kimigas --yolo
```

Gas Town communicates with crew members through **nudge** messages, delivered via `tmux send-keys`:

```sh
# Mayor or another agent sends a message
gt nudge myproject/koder "Refactor the auth module to use JWT tokens"
```

The message appears at Kimi's prompt and is submitted for processing. Kimi reads the project's `AGENTS.md`, understands the codebase, and executes the task using its full tool suite (Shell, ReadFile, WriteFile, Grep, etc.).

**Sling work to crew:**

```sh
gt sling mp-42 myproject/koder --agent kimigas
```

### Wire mode (programmatic control)

Wire mode exposes the full [JSON-RPC 2.0 protocol](../customization/wire-mode.md) for structured bidirectional communication. This is ideal for building custom orchestrators or when Gas Town needs fine-grained control over the agent.

**Starting a wire session:**

```sh
kimigas --wire --work-dir /path/to/project
```

**Handshake with external tool registration:**

```json
{"jsonrpc":"2.0","method":"initialize","id":"1","params":{"protocol_version":"1.1","client":{"name":"gastown","version":"0.5.0"},"external_tools":[{"name":"gt_notify","description":"Notify Gas Town mayor","parameters":{"type":"object","properties":{"message":{"type":"string"}},"required":["message"]}}]}}
```

**Sending a prompt:**

```json
{"jsonrpc":"2.0","method":"prompt","id":"2","params":{"user_input":"Fix the failing test in test_auth.py"}}
```

During execution, Kimi emits `event` notifications (thinking, tool calls, results) and may send `request` messages for approval or external tool execution. The wire client collects events until it receives the prompt response:

```json
{"jsonrpc":"2.0","id":"2","result":{"status":"finished"}}
```

**Key wire events for Gas Town integration:**

| Event type | Description | Gas Town use |
|------------|-------------|--------------|
| `TurnBegin` | Agent turn started | Track active work |
| `ContentPart` | AI text/thinking output | Display in dashboard |
| `ToolCall` | Agent calling a tool | Monitor tool usage |
| `ToolResult` | Tool execution result | Collect work artifacts |
| `StatusUpdate` | Context usage, token stats | Resource monitoring |
| `ApprovalRequest` | Agent needs approval | Auto-approve in yolo mode |
| `ToolCallRequest` | External tool invocation | Handle gastown-specific tools |
| `TurnEnd` | Agent turn completed | Mark work as done |

**Auto-approving in wire mode:**

When an `ApprovalRequest` arrives, respond with:

```json
{"jsonrpc":"2.0","id":"<request-id>","result":{"request_id":"<approval-id>","response":"approve"}}
```

For a full protocol reference, see the [Wire Mode documentation](../customization/wire-mode.md).

### Print mode (polecats and batch work)

Print mode with streaming JSON is ideal for ephemeral polecat workers and batch processing. It provides a persistent session over stdin/stdout where each JSON line is a user message, and responses are streamed back as JSON lines.

**Single-shot task (polecat):**

```sh
kimigas --print -p "Add error handling to the database module"
```

**Multi-turn streaming session:**

```sh
printf '{"role":"user","content":"What files are in src/?"}\n' \
       '{"role":"user","content":"Refactor utils.py to use dataclasses"}\n' \
  | kimigas --print --input-format stream-json --output-format stream-json
```

Each user message produces a JSON response with the assistant's output:

```json
{"role":"assistant","content":[{"type":"text","text":"Here are the files in src/..."}]}
```

**Pipeline integration:**

```sh
# Feed work items from Gas Town beads into kimi
bd ready --json | jq -r '.[] | {"role":"user","content":("Fix: " + .title)} | @json' \
  | kimigas --print --input-format stream-json --output-format stream-json
```

## Gas Town architecture mapping

Here is how Kimi Code CLI maps to Gas Town concepts:

| Gas Town concept | Kimi integration |
|-----------------|------------------|
| **Agent** | `kimigas --yolo` registered via `gt config agent set` |
| **Rig** | Git repo added via `gt rig add`, kimi works in crew/polecat directories |
| **Crew** | Interactive `kimi --yolo` session in tmux, receives nudges |
| **Polecat** | One-shot `kimi --print -p "task"` or streaming JSON session |
| **Hook** | Kimi reads `AGENTS.md` for project context on startup |
| **Nudge** | Text delivered via `gt nudge` → tmux → kimi's prompt |
| **Sling** | `gt sling <bead> <rig> --agent kimigas` dispatches work |
| **AGENTS.md** | Kimi natively reads `AGENTS.md` for project instructions |

## Configuration

### Kimi config for Gas Town

Create or edit `~/.kimi/config.toml`:

```toml
# Auto-approve all actions (equivalent to --yolo at startup)
default_yolo = true

# Enable thinking mode for better reasoning
default_thinking = true

# Increase max steps for complex tasks
[loop_control]
max_steps_per_turn = 100
max_retries_per_step = 3
```

### Gas Town agent configuration

In your Gas Town workspace settings (`~/gt/settings/agents.json`), add kimigas to the role configuration:

```json
{
  "role_agents": {
    "crew": "kimigas",
    "polecat": "kimigas"
  }
}
```

Or override per-sling:

```sh
gt sling mp-42 myproject --agent kimigas
```

### AGENTS.md compatibility

Kimi Code CLI natively reads `AGENTS.md` files, which is the standard project instruction file in Gas Town. If your project uses `CLAUDE.md` (for Claude Code agents), the `kimigas` adapter automatically creates a symlink when running inside Gas Town:

```
CLAUDE.md → AGENTS.md (symlinked by kimigas when GT_ROLE is set)
```

## Prompt-toolkit compatibility

Kimi Code CLI's interactive shell uses [prompt-toolkit](https://python-prompt-toolkit.readthedocs.io/) for its TUI. When Gas Town delivers messages via `tmux send-keys`, the Enter key must always submit the prompt rather than accepting autocompletions.

The [gastown-publish/kimi-cli](https://github.com/gastown-publish/kimi-cli) fork includes a patch that moves completion acceptance from Enter to Tab, ensuring reliable message delivery from `gt nudge`. If you're using the upstream kimi-cli, nudged messages may require an extra Enter to submit.

**The patch** (in `src/kimi_cli/ui/shell/prompt.py`):

```python
# Tab accepts completions (was Enter in upstream)
@_kb.add("tab", filter=has_completions)
def _(event):
    buff = event.current_buffer
    if buff.complete_state and buff.complete_state.completions:
        completion = buff.complete_state.current_completion
        if not completion:
            completion = buff.complete_state.completions[0]
        buff.apply_completion(completion)

# Enter always submits (dismisses completions first)
@_kb.add("enter", filter=has_completions)
def _(event):
    buff = event.current_buffer
    buff.cancel_completion()
    buff.validate_and_handle()
```

## Comparison with other Gas Town agents

| Feature | kimigas | claude | codex | cursor |
|---------|---------|--------|-------|--------|
| Command | `kimigas --yolo` | `claude --dangerously-skip-permissions` | `codex --yolo` | `cursor-agent -f` |
| Model | Kimi K2.5 | Claude Opus 4.6 | GPT-4.1 | Auto-selected |
| Wire protocol | JSON-RPC 2.0 | Proprietary | N/A | N/A |
| Print/streaming | `--print --input-format stream-json` | `--print` | N/A | N/A |
| Native AGENTS.md | Yes | No (reads CLAUDE.md) | No | No |
| External tools | Via wire `initialize` | Via MCP | N/A | N/A |
| Thinking mode | Yes (`--thinking`) | Yes (extended thinking) | N/A | N/A |
| Web search | Built-in (`SearchWeb`) | Via MCP | N/A | N/A |

## Example: full workflow

This end-to-end example sets up a kimigas crew member and dispatches work:

```sh
# 1. Register agent
cd ~/gt
gt config agent set kimigas "kimigas --yolo"

# 2. Add rig (if not already added)
gt rig add myapp https://github.com/org/myapp.git --prefix ma

# 3. Create crew workspace
gt crew add koder --rig myapp

# 4. Start crew with kimigas
gt crew start myapp koder --agent kimigas

# 5. Dispatch work
gt sling ma-42 myapp/koder --agent kimigas

# 6. Send follow-up instructions
gt nudge myapp/koder "Focus on the auth module first, then write tests"

# 7. Check status
gt crew list --rig myapp
```

## Troubleshooting

### Kimi not found

```
Error: kimi-cli not found
```

Install kimi-cli:

```sh
uv tool install --python 3.13 kimi-cli
```

### LLM not configured

```
Error: LLM is not set
```

Run `kimi login` to authenticate with Kimi Code, or configure an API key in `~/.kimi/config.toml`.

### Nudge text not auto-submitting

If `gt nudge` delivers text but kimi doesn't process it, the prompt-toolkit completion popup may be intercepting Enter. Use the [gastown-publish/kimi-cli](https://github.com/gastown-publish/kimi-cli) fork which patches this behavior, or send an extra Enter:

```sh
tmux send-keys -t <session> Enter
```

### Session crashes on startup

If kimi exits immediately when started by Gas Town, check:

1. Authentication: `kimi --version` and `kimi login`
2. Python version: kimi-cli requires Python 3.12+
3. Logs: `~/.kimi/logs/kimi.log`

### Wire mode timeout

If wire mode prompts take too long, increase the step limits:

```sh
kimigas --wire --max-steps-per-turn 200
```

Or in `~/.kimi/config.toml`:

```toml
[loop_control]
max_steps_per_turn = 200
```
