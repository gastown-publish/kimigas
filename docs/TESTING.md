# Testing Guidelines for kimigas

## Testing Commands in Isolated Environments

**IMPORTANT**: When testing new commands (especially those that interact with external tools like Claude Code, CCR, etc.), tests MUST be run in Docker or other isolated environments to avoid interference from the current system setup.

### Why?

- The development machine may have pre-installed tools (claude, ccr) that mask missing dependency checks
- Environment variables and configs from the host can leak into tests
- Port conflicts may occur if services are already running
- Tests may pass locally but fail on clean machines

### Docker Testing Template

```dockerfile
FROM node:20-slim

# Install Python and dependencies
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-venv \
    curl git \
    && rm -rf /var/lib/apt/lists/*

# Install external tools (the command under test should install/check these)
RUN npm install -g @anthropic-ai/claude-code
RUN pip3 install claude-code-router --break-system-packages

# Copy and install the local code
COPY . /test/
RUN cd /test && pip3 install -e . --break-system-packages

# Run tests
CMD ["/test/test_script.sh"]
```

### Testing Checklist

- [ ] Test in a clean Docker container
- [ ] Verify all dependencies are checked (claude, ccr, etc.)
- [ ] Verify graceful error messages when dependencies missing
- [ ] Verify port detection works (reads from CCR config)
- [ ] Test auto-start behavior
- [ ] Test with `--no-auto-start-ccr` flag

### Example: Testing `kimigas run claude`

```bash
# Build test image
docker build -f test_run_claude.dockerfile -t kimigas-test .

# Run tests
docker run --rm kimigas-test

# Interactive test
docker run --rm -it kimigas-test bash
$ kimi run claude --help
```

## Unit Testing

For unit tests that don't require external dependencies, use the standard pytest approach:

```bash
uv run pytest tests/ -v
```

## Integration Testing

For integration tests with external services, use Docker Compose or mock servers.
