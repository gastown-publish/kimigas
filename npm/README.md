# kimigas

Kimi Code CLI for [Gas Town](https://github.com/steveyegge/gastown) — an AI agent for terminal-based software development and multi-agent orchestration.

This is the Gas Town fork of [kimi-cli](https://github.com/MoonshotAI/kimi-cli) by MoonshotAI, with tmux compatibility, message queuing, and multi-agent support.

## Install

```sh
npm install -g kimigas
```

## Other installation methods

```sh
# Homebrew
brew install gastown-publish/tap/kimigas

# pip
pip install kimigas

# apt (Debian/Ubuntu)
# Download .deb from GitHub releases
curl -LO https://github.com/gastown-publish/kimigas/releases/latest/download/kimigas_VERSION_amd64.deb
sudo dpkg -i kimigas_*.deb
```

## Usage

```sh
kimigas              # Interactive mode
kimigas -p "task"    # One-shot mode
kimigas --yolo       # Auto-approve all actions (for Gas Town agents)
```

## Links

- [GitHub](https://github.com/gastown-publish/kimigas)
- [Gas Town](https://github.com/steveyegge/gastown)
- [Upstream kimi-cli](https://github.com/MoonshotAI/kimi-cli)
