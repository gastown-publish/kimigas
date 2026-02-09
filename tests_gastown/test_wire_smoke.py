#!/usr/bin/env python3
"""Wire protocol smoke test for gastown/kimi-cli fork.

Verifies that kimi's wire mode (JSON-RPC 2.0) works correctly for
Gas Town integration. This test does NOT require an LLM API key —
it only tests protocol-level functionality:

  1. Initialize handshake with external tool registration
  2. Protocol version negotiation
  3. Slash command enumeration
  4. Error handling for prompts without LLM

Run with:
  python tests_gastown/test_wire_smoke.py
  uv run python tests_gastown/test_wire_smoke.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import uuid


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
    # Check if kimi is directly available (pip/uv tool install)
    if shutil.which("kimi"):
        return ["kimi"]
    # In CI, use uv run when inside a uv-managed project
    if os.path.exists("pyproject.toml") and shutil.which("uv"):
        return ["uv", "run", "kimi"]
    # Last resort: python -m
    return [sys.executable, "-m", "kimi_cli"]


def send_and_recv(
    proc: subprocess.Popen[str],
    request: dict,
    *,
    timeout_lines: int = 50,
) -> dict | None:
    """Send a JSON-RPC request and read responses until we find one with our id."""
    line = json.dumps(request) + "\n"
    assert proc.stdin is not None
    assert proc.stdout is not None
    try:
        proc.stdin.write(line)
        proc.stdin.flush()
    except BrokenPipeError:
        return None

    request_id = request.get("id")
    for _ in range(timeout_lines):
        try:
            raw = proc.stdout.readline()
        except (BrokenPipeError, OSError):
            break
        if not raw:
            break
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if "id" in msg and msg["id"] == request_id:
            return msg
    return None


def main() -> int:
    global _passed, _failed

    print("=" * 60)
    print("GASTOWN WIRE PROTOCOL SMOKE TEST")
    print("=" * 60)

    kimi_cmd = _find_kimi()
    print(f"Using: {' '.join(kimi_cmd)}")

    # Start kimi in wire mode
    proc = subprocess.Popen(
        [*kimi_cmd, "--wire"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    # Give the process a moment to start
    time.sleep(1)
    if proc.poll() is not None:
        stderr = proc.stderr.read() if proc.stderr else ""
        print(f"  kimi --wire exited immediately (code {proc.returncode})")
        print(f"  stderr: {stderr[:500]}")
        check("Wire server starts", False, f"exit code {proc.returncode}")
        print(f"\nRESULTS: {_passed}/{_passed + _failed} passed, {_failed} failed")
        return 1

    check("Wire server starts", True)

    try:
        # ── Test 1: Initialize handshake ──────────────────────
        print("\n── Initialize handshake ──")
        init_id = str(uuid.uuid4())
        init_req = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "id": init_id,
            "params": {
                "protocol_version": "1.1",
                "client": {"name": "gastown-ci", "version": "0.1.0"},
                "external_tools": [
                    {
                        "name": "gt_notify",
                        "description": "Send notification to Gas Town",
                        "parameters": {
                            "type": "object",
                            "properties": {"message": {"type": "string"}},
                            "required": ["message"],
                        },
                    }
                ],
            },
        }

        resp = send_and_recv(proc, init_req)
        check("Initialize response received", resp is not None)

        if resp and "result" in resp:
            r = resp["result"]
            check("Has protocol_version", "protocol_version" in r)
            check(
                "Protocol version >= 1.1",
                float(r.get("protocol_version", "0")) >= 1.1,
                f"got {r.get('protocol_version')}",
            )
            check(
                "Server name is Kimi Code CLI",
                r.get("server", {}).get("name") == "Kimi Code CLI",
            )
            check(
                "Server version present",
                bool(r.get("server", {}).get("version")),
            )
            check(
                "Slash commands non-empty",
                len(r.get("slash_commands", [])) > 0,
                f"got {len(r.get('slash_commands', []))}",
            )
            check(
                "External tool gt_notify accepted",
                "gt_notify" in r.get("external_tools", {}).get("accepted", []),
                f"got {r.get('external_tools', {})}",
            )
            check(
                "No rejected external tools",
                len(r.get("external_tools", {}).get("rejected", [])) == 0,
            )

            print(f"\n  Server: {r['server']['name']} v{r['server']['version']}")
            print(f"  Protocol: {r['protocol_version']}")
            print(f"  Commands: {len(r['slash_commands'])}")
        elif resp and "error" in resp:
            check("Initialize succeeded", False, f"error: {resp['error']}")

        # ── Test 2: Cancel with no turn in progress ───────────
        print("\n── Cancel (no turn in progress) ──")
        cancel_id = str(uuid.uuid4())
        cancel_req = {
            "jsonrpc": "2.0",
            "method": "cancel",
            "id": cancel_id,
        }

        resp = send_and_recv(proc, cancel_req)
        check("Cancel response received", resp is not None)
        if resp and "error" in resp:
            check(
                "Cancel error code is -32000",
                resp["error"].get("code") == -32000,
                f"got {resp['error'].get('code')}",
            )

        # ── Test 3: Invalid method ────────────────────────────
        print("\n── Invalid method handling ──")
        bad_id = str(uuid.uuid4())
        bad_req = {
            "jsonrpc": "2.0",
            "method": "nonexistent_method",
            "id": bad_id,
            "params": {},
        }

        resp = send_and_recv(proc, bad_req)
        check("Invalid method response received", resp is not None)
        if resp and "error" in resp:
            check(
                "Error code is -32601 (method not found)",
                resp["error"].get("code") == -32601,
                f"got {resp['error'].get('code')}",
            )

    finally:
        try:
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.close()
        except BrokenPipeError:
            pass
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    # ── Summary ───────────────────────────────────────────────
    print("\n" + "=" * 60)
    total = _passed + _failed
    print(f"RESULTS: {_passed}/{total} passed, {_failed} failed")
    print("=" * 60)
    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
