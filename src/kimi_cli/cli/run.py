"""Run command for Kimi Code CLI - run other CLI tools with Kimi backend."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Annotated

import typer

from kimi_cli.utils.subprocess_env import get_clean_env

cli = typer.Typer(help="Run other CLI tools with Kimi backend.")

# CCR (claude-code-router) configuration defaults
_CCR_DEFAULT_HOST = "127.0.0.1"
_CCR_DEFAULT_PORT = 8180
_CCR_START_TIMEOUT = 10  # seconds


def _get_ccr_config() -> tuple[str, int]:
    """Get CCR host and port from config file or defaults."""
    config_path = Path.home() / ".claude-code-router" / "config.json"
    try:
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                config = json.load(f)
            host = config.get("HOST", _CCR_DEFAULT_HOST)
            port = config.get("PORT", _CCR_DEFAULT_PORT)
            return host, port
    except Exception:
        pass
    return _CCR_DEFAULT_HOST, _CCR_DEFAULT_PORT


def _is_ccr_running(host: str, port: int) -> bool:
    """Check if claude-code-router is running."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def _start_ccr() -> bool:
    """Start claude-code-router if available."""
    ccr_path = shutil.which("ccr")
    if ccr_path is None:
        return False

    try:
        # Start CCR in background
        subprocess.Popen(
            [ccr_path, "start"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        # Get the configured host/port
        host, port = _get_ccr_config()

        # Wait for CCR to be ready
        for _ in range(_CCR_START_TIMEOUT):
            if _is_ccr_running(host, port):
                return True
            time.sleep(1)

        return False
    except Exception:
        return False


def _find_claude_binary() -> str | None:
    """Find the claude binary in PATH."""
    return shutil.which("claude")


@cli.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)
def claude(
    ctx: typer.Context,
    work_dir: Annotated[
        Path | None,
        typer.Option(
            "--work-dir",
            "-w",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            writable=True,
            help="Working directory for Claude Code. Default: current directory.",
        ),
    ] = None,
    yolo: Annotated[
        bool,
        typer.Option(
            "--yolo",
            "--yes",
            "-y",
            "--auto-approve",
            help="Automatically approve all actions. Default: no.",
        ),
    ] = False,
    dangerous_skip_permissions: Annotated[
        bool,
        typer.Option(
            "--dangerously-skip-permissions",
            help="Skip all permission checks (use with caution).",
        ),
    ] = False,
    no_auto_start_ccr: Annotated[
        bool,
        typer.Option(
            "--no-auto-start-ccr",
            help="Don't automatically start claude-code-router if not running.",
        ),
    ] = False,
):
    """Run Claude Code with Kimi backend via claude-code-router.

    This command launches Claude Code but redirects all API calls to Kimi K2.5
    through claude-code-router. This allows you to use Claude Code's interface
    with Kimi's model.

    Requires:
        - claude: Anthropic's Claude Code CLI (npm install -g @anthropic-ai/claude-code)
        - ccr: claude-code-router (pip install claude-code-router)

    Examples:
        kimigas run claude                    # Run Claude Code with Kimi backend
        kimigas run claude --yolo             # Auto-approve all actions
        kimigas run claude -w /path/to/project  # Set working directory
    """
    # Check if claude is installed
    claude_path = _find_claude_binary()
    if claude_path is None:
        typer.echo(
            "Error: Claude Code not found. Install it with:\n"
            "  npm install -g @anthropic-ai/claude-code",
            err=True,
        )
        raise typer.Exit(code=1)

    # Check if CCR is installed
    if shutil.which("ccr") is None:
        typer.echo(
            "Error: claude-code-router not found. Install it with:\n"
            "  pip install claude-code-router",
            err=True,
        )
        raise typer.Exit(code=1)

    # Get CCR config (host/port from config file or defaults)
    ccr_host, ccr_port = _get_ccr_config()
    ccr_base_url = f"http://{ccr_host}:{ccr_port}/v1"

    # Check if CCR is running, start it if needed
    if not _is_ccr_running(ccr_host, ccr_port):
        if no_auto_start_ccr:
            typer.echo(
                f"Error: claude-code-router is not running at {ccr_base_url}.\n"
                "Start it with: ccr start",
                err=True,
            )
            raise typer.Exit(code=1)

        typer.echo("Starting claude-code-router...")
        if not _start_ccr():
            typer.echo(
                "Error: Failed to start claude-code-router.\n"
                "Start it manually with: ccr start",
                err=True,
            )
            raise typer.Exit(code=1)
        typer.echo(f"claude-code-router ready at {ccr_base_url}")

    # Build environment with Claude Code redirected to CCR
    # Following Ollama's pattern from cmd/config/claude.go
    env = get_clean_env()
    env.update({
        # Redirect Anthropic API to CCR
        "ANTHROPIC_BASE_URL": ccr_base_url,
        "ANTHROPIC_API_KEY": "",  # CCR handles auth
        "ANTHROPIC_AUTH_TOKEN": "claude-code-router",
        # Map Claude model aliases to Kimi models via CCR
        "ANTHROPIC_DEFAULT_OPUS_MODEL": "kimi-k2.5",
        "ANTHROPIC_DEFAULT_SONNET_MODEL": "kimi-k2.5",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": "kimi-k2.5",
        "CLAUDE_CODE_SUBAGENT_MODEL": "kimi-k2.5",
        # Tell CCR which provider to use (if supported)
        "CCR_PROVIDER": "local",  # Use local Kimi K2.5
    })

    # Build claude command arguments
    claude_args = [claude_path]

    if yolo:
        claude_args.append("--yolo")

    if dangerous_skip_permissions:
        claude_args.append("--dangerously-skip-permissions")

    if work_dir is not None:
        claude_args.extend(["--work-dir", str(work_dir)])

    # Pass through any additional arguments
    claude_args.extend(ctx.args)

    # Launch Claude Code with modified environment
    typer.echo(f"Launching Claude Code with Kimi backend...")

    try:
        # Use os.execvpe to replace current process with claude
        # This ensures proper TTY handling for interactive CLI
        os.execvpe(claude_args[0], claude_args, env)
    except OSError as e:
        typer.echo(f"Error launching Claude Code: {e}", err=True)
        raise typer.Exit(code=1)
