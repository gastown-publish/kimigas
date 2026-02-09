# Integrations with Tools

Besides using in the terminal and IDEs, Kimi Code CLI can also be integrated with other tools.

## Gas Town (multi-agent orchestration)

Kimi Code CLI can run as a first-class agent in [Gas Town](https://github.com/steveyegge/gastown), a multi-agent orchestration system. It supports three integration modes: interactive shell (crew workers), wire protocol (programmatic control), and print mode (ephemeral polecats).

See the dedicated [Gas Town Integration](./gastown.md) guide for full setup instructions.

## Zsh plugin

[zsh-kimi-cli](https://github.com/MoonshotAI/zsh-kimi-cli) is a Zsh plugin that lets you quickly switch to Kimi Code CLI in Zsh.

**Installation**

If you use Oh My Zsh, you can install it like this:

```sh
git clone https://github.com/MoonshotAI/zsh-kimi-cli.git \
  ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/kimi-cli
```

Then add the plugin in `~/.zshrc`:

```sh
plugins=(... kimi-cli)
```

Reload the Zsh configuration:

```sh
source ~/.zshrc
```

**Usage**

After installation, press `Ctrl-X` in Zsh to quickly switch to Kimi Code CLI without manually typing the `kimi` command.

::: tip
If you use other Zsh plugin managers (like zinit, zplug, etc.), please refer to the [zsh-kimi-cli repository](https://github.com/MoonshotAI/zsh-kimi-cli) README for installation instructions.
:::
