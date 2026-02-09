#!/usr/bin/env python3
"""Print mode smoke test for gastown/kimi-cli fork.

Verifies that kimi's print mode with streaming JSON works correctly
for Gas Town polecat/batch integration. This test does NOT require
an LLM API key — it tests that the CLI starts, accepts flags, and
that the gastown patch is present in the source code.

Run with:
  python tests_gastown/test_print_smoke.py
  uv run python tests_gastown/test_print_smoke.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
_passed = 0
_failed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global _passed, _failed
    if condition:
        print(f"  {PASS} {name}")
        _passed += 1
    else:
        print(f"  {FAIL} {name} {detail}")
        _failed += 1


def _find_kimi() -> list[str]:
    """Find the kimi command — prefer kimi from PATH, fall back to uv run."""
    if shutil.which("kimi"):
        return ["kimi"]
    if os.path.exists("pyproject.toml") and shutil.which("uv"):
        return ["uv", "run", "kimi"]
    return [sys.executable, "-m", "kimi_cli"]


def _find_prompt_py() -> Path | None:
    """Find prompt.py in the source tree or installed package."""
    # Check source tree first (running from repo root)
    src = Path("src/kimi_cli/ui/shell/prompt.py")
    if src.exists():
        return src

    # Try installed package
    try:
        import importlib.util

        spec = importlib.util.find_spec("kimi_cli.ui.shell.prompt")
        if spec and spec.origin:
            return Path(spec.origin)
    except (ImportError, ModuleNotFoundError):
        pass

    return None


def main() -> int:
    global _passed, _failed

    print("=" * 60)
    print("GASTOWN PRINT MODE SMOKE TEST")
    print("=" * 60)

    kimi_cmd = _find_kimi()
    print(f"Using: {' '.join(kimi_cmd)}")

    # ── Test 1: --version flag works ──────────────────────────
    print("\n── Version check ──")
    result = subprocess.run(
        [*kimi_cmd, "--version"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    check("Version command exits 0", result.returncode == 0)
    version_output = result.stdout.strip()
    check(
        "Version output contains 'kimi'",
        "kimi" in version_output.lower(),
        f"got: {version_output!r}",
    )
    if result.returncode == 0:
        print(f"  Version: {version_output}")

    # ── Test 2: --help flag works ─────────────────────────────
    print("\n── Help check ──")
    result = subprocess.run(
        [*kimi_cmd, "--help"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    check("Help command exits 0", result.returncode == 0)
    help_text = result.stdout
    check("Help mentions --yolo", "--yolo" in help_text)
    check("Help mentions --wire", "--wire" in help_text)
    check("Help mentions --print", "--print" in help_text)
    check("Help mentions --input-format", "--input-format" in help_text)

    # ── Test 3: Print mode starts and accepts stream-json ─────
    print("\n── Print mode with stream-json ──")
    user_msg = json.dumps({"role": "user", "content": "Say hello"})

    result = subprocess.run(
        [*kimi_cmd, "--print", "--input-format", "stream-json", "--output-format", "stream-json"],
        input=user_msg + "\n",
        capture_output=True,
        text=True,
        timeout=30,
    )

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()

    if result.returncode == 0 and stdout:
        # If it succeeded (has API key), verify JSON output
        try:
            first_line = stdout.split("\n")[0]
            parsed = json.loads(first_line)
            check("Output is valid JSON", True)
            check(
                "Output has role field",
                "role" in parsed,
                f"got keys: {list(parsed.keys())}",
            )
            check(
                "Role is assistant",
                parsed.get("role") == "assistant",
                f"got: {parsed.get('role')}",
            )
        except json.JSONDecodeError:
            check("Output is valid JSON", False, f"got: {first_line!r}")
    else:
        # Without API key, verify graceful exit (no Python crash)
        has_crash = "Traceback (most recent call last)" in stderr and "raise" in stderr
        is_expected_error = any(
            msg in stderr for msg in ["LLM is not set", "ConfigError", "not configured"]
        )
        check(
            "Graceful exit without API key",
            not has_crash or is_expected_error,
            f"stderr tail: {stderr[-200:]}",
        )
        print(f"  Note: exit code {result.returncode} (expected without API key)")

    # ── Test 4: Verify prompt.py gastown patch ────────────────
    print("\n── Gastown patch verification ──")
    prompt_py = _find_prompt_py()
    check("prompt.py found", prompt_py is not None, "could not locate prompt.py")

    if prompt_py:
        source = prompt_py.read_text(encoding="utf-8")
        check(
            "Tab keybinding for completions",
            'add("tab", filter=has_completions)' in source
            or "add('tab', filter=has_completions)" in source,
            "Tab completion acceptance not found",
        )
        check(
            "Enter submits with completions (gastown patch)",
            "cancel_completion" in source and "validate_and_handle" in source,
            "Enter-submit-with-completions patch not found",
        )
        check(
            "Gas Town compatibility comment present",
            "Gas Town" in source,
            "Patch comment not found in source",
        )
        print(f"  Source: {prompt_py}")

    # ── Summary ───────────────────────────────────────────────
    print("\n" + "=" * 60)
    total = _passed + _failed
    print(f"RESULTS: {_passed}/{total} passed, {_failed} failed")
    print("=" * 60)
    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
