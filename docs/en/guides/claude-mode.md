# Claude Code Mode

Run Claude Code with Kimi K2.5 as the underlying LLM engine for a powerful hybrid experience.

## Overview

Claude Code mode (`--claude`) launches **Claude Code** (Anthropic's CLI coding agent) with **Kimi K2.5** as the backend LLM. This gives you:

- **Claude Code's UI**: Interactive shell with syntax highlighting and tool orchestration
- **Kimi K2.5's intelligence**: Advanced reasoning and code generation capabilities
- **Native compatibility**: Kimi's Anthropic-compatible API endpoint requires no proxy

## Prerequisites

Before using `--claude` mode, ensure you have:

1. **Claude Code installed**:
   ```bash
   npm install -g @anthropic-ai/claude-code
   ```

2. **Kimi API key** configured (one of):
   - Set `KIMI_API_KEY` environment variable
   - Use `--api-key` option
   - Run `kimi login` to authenticate

3. **kimigas installed** from the fork:
   ```bash
   uv tool install git+https://github.com/gastown-publish/kimigas.git
   ```

## Quick Start

### Basic Usage

```bash
# Launch Claude Code with Kimi backend
kimigas --claude

# Auto-approve all actions (non-interactive)
kimigas --claude --yolo

# Run a one-shot task
kimigas --claude -p "refactor the auth module"

# Set working directory
kimigas --claude -w /path/to/project
```

### Using the `run claude` Subcommand

The `--claude` flag is a shorthand for:

```bash
kimigas run claude              # Same as --claude
kimigas run claude --yolo       # Same as --claude --yolo
kimigas run claude -p "task"    # Same as --claude -p "task"
```

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                  CLAUDE CODE + KIMI K2.5                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    Anthropic API format    ┌───────────┐  │
│  │ Claude Code │ ◄────────────────────────► │ Kimi K2.5 │  │
│  │   (CLI)     │                            │   API     │  │
│  │             │  ANTHROPIC_BASE_URL=       │           │  │
│  │  • Tools    │  https://api.kimi.com/     │ • Reason  │  │
│  │  • UI       │       coding/              │ • Generate│  │
│  │  • Agent    │                            │ • 128k ctx│  │
│  └─────────────┘                            └───────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

Kimi provides a native Anthropic-compatible endpoint at `https://api.kimi.com/coding/`. When you use `--claude` mode:

1. `kimigas` sets `ANTHROPIC_BASE_URL` to Kimi's endpoint
2. Your Kimi API key is passed as `ANTHROPIC_API_KEY`
3. Claude Code connects directly to Kimi instead of Anthropic
4. All tool calls and responses work seamlessly

## Configuration

### API Key

The `--claude` mode looks for your Kimi API key in this order:

1. `--api-key` option: `kimigas --claude --api-key sk-kimi-...`
2. `KIMI_API_KEY` environment variable
3. Existing `kimi login` credentials

### Environment Variables

You can also run Claude Code directly with Kimi by setting environment variables:

```bash
export ANTHROPIC_BASE_URL="https://api.kimi.com/coding/"
export ANTHROPIC_API_KEY="sk-kimi-YOUR_KEY"

claude --dangerously-skip-permissions
```

The `kimigas --claude` command handles this automatically.

## Common Use Cases

### Interactive Development

```bash
# Start interactive session
kimigas --claude

# In Claude Code, you can:
# - Ask questions about your codebase
# - Request code changes
# - Run tests and commands
# - Use / commands for special actions
```

### One-Shot Tasks

```bash
# Quick code review
kimigas --claude -p "review the main.py file for bugs"

# Generate documentation
kimigas --claude -p "generate README.md for this project"

# Refactoring
kimigas --claude -p "refactor auth.py to use dependency injection"
```

### Gas Town Integration

For Gas Town multi-agent orchestration:

```bash
# Set as default agent with auto-approval
gt config agent set kimigas "kimigas --claude --yolo"

# Start crew worker
gt crew start myrig myname --agent kimigas

# Sling work to polecat
gt sling gt-abc myrig --agent kimigas
```

## Options Reference

| Option | Description |
|--------|-------------|
| `--claude` | Enable Claude Code mode |
| `--yolo`, `-y` | Auto-approve all actions (maps to `--dangerously-skip-permissions`) |
| `-p`, `--prompt` | Run a one-shot task and exit |
| `-w`, `--work-dir` | Set the working directory |
| `--api-key` | Specify Kimi API key |

## Troubleshooting

### "No such option: --claude" Error

**Cause**: You're using the upstream `kimi-cli` package instead of `kimigas`.

**Solution**: Install from the gastown-publish fork:

```bash
uv tool uninstall kimi-cli  # Remove upstream version
uv tool install git+https://github.com/gastown-publish/kimigas.git
```

### "Claude Code not found" Error

**Cause**: Claude Code CLI is not installed.

**Solution**: Install Claude Code:

```bash
npm install -g @anthropic-ai/claude-code
```

### API Key Not Recognized

**Cause**: Claude Code is trying to use OAuth instead of API key.

**Solution**: `kimigas` handles this automatically by using an isolated config directory. If running `claude` directly, ensure you use a separate config dir:

```bash
export CLAUDE_CONFIG_DIR="$HOME/.claude-kimigas"
export ANTHROPIC_BASE_URL="https://api.kimi.com/coding/"
export ANTHROPIC_API_KEY="sk-kimi-..."
claude --dangerously-skip-permissions
```

### Connection Issues

Verify your API key works:

```bash
curl https://api.kimi.com/coding/v1/models \
  -H "Authorization: Bearer $ANTHROPIC_API_KEY"
```

## Comparison: Native Kimi vs Claude Mode

| Feature | Native `kimigas` | `--claude` Mode |
|---------|------------------|-----------------|
| UI | Custom shell | Claude Code UI |
| Tools | Kimi native | Claude's tools |
| Approval | Interactive | Interactive or `--yolo` |
| Best for | Kimi users | Claude Code users |

## See Also

- [Claude Code + Kimi Integration](../../CLAUDE_CODE_KIMI_INTEGRATION.md) - Detailed architecture
- [Gas Town Integration](./gastown.md) - Multi-agent orchestration
- [Claude Code Docs](https://docs.anthropic.com/en/docs/claude-code/overview)
