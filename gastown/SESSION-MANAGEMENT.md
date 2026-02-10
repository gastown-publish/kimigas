# Gas Town Session Management & Auto-Monitor

A complete guide for configuring zero-downtime agent sessions on any Gas Town server using KimiGas.

## Architecture

Gas Town runs agents in tmux sessions. Each session hosts one long-lived process — either `claude` (Claude Code) or `kimi` (Kimi Code via the `kimigas` wrapper). The automonitor loop keeps everything alive.

```
┌─────────────────────────────────────────────────────────┐
│  tmux server                                            │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ hq-mayor     │  │ hq-deacon    │  │ gt-automonitor│  │
│  │ (claude/kimi)│  │ (kimi)       │  │ (bash loop)  │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐                     │
│  │ gt-<rig>-    │  │ gt-<rig>-    │                     │
│  │  witness     │  │  refinery    │                     │
│  │ (kimi)       │  │ (kimi)       │                     │
│  └──────────────┘  └──────────────┘                     │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ gt-<rig>-    │  │ gt-<rig>-    │  │ gt-<rig>-    │  │
│  │ crew-uitester│  │ crew-watcher │  │ crew-*       │  │
│  │ (kimi)       │  │ (kimi)       │  │ (kimi)       │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
         ▲                                    ▲
         │           automonitor              │
         └──── restarts dead sessions ────────┘
```

## Session Types

| Session Pattern | Role | Started By | Restart Command |
|---|---|---|---|
| `hq-mayor` | Town coordinator | `gt mayor attach` | `gt mayor restart` |
| `hq-deacon` | Task dispatcher | `gt deacon start` | `gt deacon restart` |
| `gt-<rig>-witness` | Code reviewer | `gt witness start <rig>` | `gt witness restart <rig>` |
| `gt-<rig>-refinery` | Code refiner | `gt refinery start <rig>` | `gt refinery restart <rig>` |
| `gt-<rig>-crew-<name>` | Named worker | `gt crew at <name> -d` | `gt crew restart <name> --rig <rig>` |
| `gt-automonitor` | Health monitor | `gt-automonitor start` | `gt-automonitor restart` |

## Setting Up KimiGas as Default Agent

Configure Gas Town to use KimiGas for all roles:

```bash
# Set default agent
gt config default-agent kimigas

# Set polecat agent (ephemeral workers)
gt config polecat-agent kimigas

# Verify
gt config agent get kimigas
```

In `~/gt/settings/agents.json`, the role-agent mapping should look like:

```json
{
  "role_agents": {
    "mayor": "claude",
    "deacon": "kimigas",
    "witness": "kimigas",
    "refinery": "kimigas",
    "crew": "kimigas",
    "polecat": "kimigas"
  }
}
```

Mayor stays on `claude` because it needs the strongest reasoning. Everything else runs on `kimigas` for throughput and cost efficiency.

## Starting All Sessions

Boot the full stack in order:

```bash
# 1. Core infrastructure
gt witness start <your-rig> -d
gt refinery start <your-rig> -d

# 2. Command hierarchy
gt mayor attach -d
gt deacon start -d

# 3. Named crew
gt crew at uitester -d --rig <your-rig>
gt crew at watcher -d --rig <your-rig>

# 4. Automonitor (keeps everything alive)
gt-automonitor start
```

Verify everything is up:

```bash
tmux list-sessions
# Should show: hq-mayor, hq-deacon, gt-<rig>-witness,
#   gt-<rig>-refinery, gt-<rig>-crew-*, gt-automonitor
```

## The Automonitor

The automonitor is a bash loop that runs in its own tmux session. Every 20 minutes it performs four phases:

### Phase 1: Upstream Check
Queries GitHub for new gastown releases and commits. If a newer version is available, it logs a warning and writes `pending_upgrade.txt` for the AI analysis phase.

### Phase 2: Hourly Handoffs
Iterates every `gt-*` and `hq-*` tmux session. Any session older than 1 hour is restarted using the appropriate `gt` command. This prevents context exhaustion — agents get a fresh context window each hour.

```
Session gt-myrig-crew-uitester age: 72m (>3600s) → restart
Session hq-mayor age: 45m → OK
```

The handoff tracker (`handoffs.json`) prevents restart storms — a session won't be restarted again within 1 hour of its last handoff.

### Phase 3: Watcher Nudge (every 3rd cycle, ~1 hour)
Sends a monitoring task to the watcher crew via `tmux send-keys`. The watcher then:
- Checks upstream releases
- Checks community posts
- Reports system health
- Files beads for improvement opportunities

### Phase 4: AI Analysis (every 2nd cycle, ~40 minutes)
Gathers a full system state snapshot and passes it to `kimigas --print` for autonomous analysis. The AI can:
- Restart dead agents
- Nudge idle crews
- File new beads
- Clean stale polecats
- Document upgrade plans

### Automonitor File Layout

```
~/gt/settings/automonitor/
├── state.json              # Persistent state (cycles, upgrades, handoffs)
├── monitor.jsonl           # Structured event log
├── handoffs.json           # Last-handoff timestamp per session
├── current_state.txt       # System snapshot for AI analysis
├── pending_upgrade.txt     # Present when upgrade is available
└── ai_analysis_*.log       # AI analysis output (last 50 kept)
```

### state.json

```json
{
  "last_known_release": "v0.5.0",
  "last_known_commit": "9f57a35a93d4",
  "last_check_ts": "2026-02-10T06:05:42Z",
  "last_upgrade_ts": "",
  "cycles_run": 2,
  "upgrades_applied": 0,
  "handoffs_triggered": 5,
  "ai_analyses_run": 1
}
```

## The Automonitor Script

Place this at `~/gt/settings/gt-automonitor-loop.sh`:

```bash
#!/bin/bash
set -euo pipefail

MONITOR_DIR="$HOME/gt/settings/automonitor"
STATE_FILE="$MONITOR_DIR/state.json"
LOG_FILE="$MONITOR_DIR/monitor.jsonl"
HANDOFF_FILE="$MONITOR_DIR/handoffs.json"
CYCLE_INTERVAL=1200    # 20 minutes
HANDOFF_THRESHOLD=3600 # 1 hour

mkdir -p "$MONITOR_DIR"

# Initialize state file if missing
if [ ! -f "$STATE_FILE" ]; then
    cat > "$STATE_FILE" << 'STATEJSON'
{
  "last_known_release": "",
  "last_known_commit": "",
  "last_check_ts": "",
  "last_upgrade_ts": "",
  "cycles_run": 0,
  "upgrades_applied": 0,
  "handoffs_triggered": 0,
  "ai_analyses_run": 0
}
STATEJSON
fi

if [ ! -f "$HANDOFF_FILE" ]; then
    echo '{}' > "$HANDOFF_FILE"
fi

log_event() {
    local level="$1" component="$2" message="$3"
    local ts
    ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    printf '{"ts":"%s","level":"%s","component":"%s","message":"%s"}\n' \
        "$ts" "$level" "$component" "$message" >> "$LOG_FILE"
}

update_state() {
    local key="$1" value="$2"
    python3 -c "
import json
with open('$STATE_FILE') as f:
    state = json.load(f)
state['$key'] = $value
with open('$STATE_FILE', 'w') as f:
    json.dump(state, f, indent=2)
"
}

increment_state() {
    local key="$1"
    python3 -c "
import json
with open('$STATE_FILE') as f:
    state = json.load(f)
state['$key'] = state.get('$key', 0) + 1
with open('$STATE_FILE', 'w') as f:
    json.dump(state, f, indent=2)
"
}
```

The full script with all four phases is at `~/gt/settings/gt-automonitor-loop.sh`. The key patterns each server should replicate:

1. **Structured JSONL logging** — every action gets a timestamped log entry
2. **Handoff debounce** — track last restart time per session to prevent storms
3. **Phase gating** — expensive phases (AI analysis, watcher nudge) run on alternating cycles
4. **Graceful failures** — every phase is wrapped in `|| log_event "ERROR" ...` so one failure doesn't kill the loop

## Watcher Crew Setup

The watcher is a named crew member that monitors upstream changes and community activity. Create it on each server:

```bash
# Create the crew slot
gt crew add watcher --rig <your-rig>

# Write its instructions
mkdir -p ~/gt/<your-rig>/crew/watcher/
cat > ~/gt/<your-rig>/crew/watcher/CLAUDE.md << 'EOF'
# Watcher Crew - Gas Town Update Monitor

You are the **watcher** crew member. Your mission is to continuously monitor
Gas Town for updates, community activity, and improvement opportunities.

## Your Loop (every cycle)

### 1. Check Gas Town Releases
```bash
curl -s https://api.github.com/repos/steveyegge/gastown/releases/latest \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'Latest: {d[\"tag_name\"]} - {d[\"name\"]}')"
gt --version
```

### 2. Check Community / Blog Posts
- https://steve-yegge.medium.com/
- https://github.com/steveyegge/gastown/discussions
- https://github.com/steveyegge/gastown/issues

### 3. Monitor System Health
```bash
tmux list-sessions
bd ready | head -20
gt convoy list
```

### 4. Apply Improvements
- Suggest upgrades to mayor via `gt mail send`
- File beads for improvement opportunities: `bd create --title "..." --priority P2`
- Nudge idle crew members via tmux send-keys if they're stuck

### 5. Report
```bash
gt mail send mayor --subject "Watcher Report" --body "..."
```

## Important
- Do NOT force push or make destructive changes
- File beads for anything that needs work
- Send mail to mayor for decisions that affect the whole town
- Your cycle should take ~5-10 minutes, then wait for the next nudge
EOF

# Start it
gt crew at watcher -d --rig <your-rig>
```

## Zero Dead Sessions Guarantee

The combination of three mechanisms ensures no session stays dead:

### 1. Automonitor Phase 2 (Hourly Handoffs)
Every 20 minutes, the automonitor checks all session ages. Sessions older than 1 hour are restarted. This also catches sessions that died silently — if a session was created 70 minutes ago but the process inside exited, the restart will revive it.

### 2. Automonitor Phase 3 (Watcher Nudge)
The watcher crew runs `tmux list-sessions` during its monitoring cycle. If it notices missing sessions, it can file beads or alert the mayor.

### 3. Automonitor Phase 4 (AI Analysis)
The AI analysis receives a full system state including all tmux sessions and running processes. It can autonomously restart any dead agents.

### Verification

Run this to confirm zero dead sessions at any time:

```bash
# Check all sessions are alive (dead=0 for every pane)
for s in $(tmux list-sessions -F '#{session_name}'); do
  dead=$(tmux list-panes -t "$s" -F '#{pane_dead}')
  cmd=$(tmux list-panes -t "$s" -F '#{pane_current_command}')
  echo "$s | dead=$dead | cmd=$cmd"
done

# Expected output: every session shows dead=0
# cmd should be: claude, python (kimi), or bash (automonitor)
```

Check the automonitor is cycling:

```bash
# Last 10 log entries
tail -10 ~/gt/settings/automonitor/monitor.jsonl

# Current state
cat ~/gt/settings/automonitor/state.json

# Automonitor process
tmux list-panes -t gt-automonitor -F '#{pane_pid} #{pane_dead} #{pane_current_command}'
```

## Tuning Parameters

| Parameter | Default | Description |
|---|---|---|
| `CYCLE_INTERVAL` | 1200s (20 min) | How often the automonitor runs a cycle |
| `HANDOFF_THRESHOLD` | 3600s (1 hour) | Max session age before forced restart |
| Watcher nudge | Every 3rd cycle (~1 hour) | How often the watcher gets a monitoring task |
| AI analysis | Every 2nd cycle (~40 min) | How often AI reviews full system state |
| AI timeout | 300s (5 min) | Max time for AI analysis before abort |
| AI log retention | 50 files | Old AI analysis logs are pruned |

For high-throughput servers, consider:
- Reducing `CYCLE_INTERVAL` to 600s (10 min) for faster dead session detection
- Reducing `HANDOFF_THRESHOLD` to 1800s (30 min) for fresher context windows
- Running AI analysis every cycle instead of every other

For low-budget servers:
- Increase `CYCLE_INTERVAL` to 3600s (1 hour)
- Run AI analysis every 3rd cycle
- Skip watcher nudge (remove Phase 3)

## Troubleshooting

### Automonitor itself dies
The automonitor runs with `set -euo pipefail` but every phase is guarded with `|| log_event "ERROR" ...`. If it still dies, check:

```bash
# Is the process alive?
tmux list-panes -t gt-automonitor -F '#{pane_dead}'

# If dead, restart it
gt-automonitor restart

# Check what killed it
tail -50 ~/gt/settings/automonitor/monitor.jsonl
```

Common causes:
- `grep` returning exit code 1 when no match — add `|| true` after grep commands
- `local` keyword inside while loops causing `set -e` to trigger — use variable assignment without `local`
- `tmux capture-pane` failing on dead panes — wrap with `|| true`

### Session restarts in a loop
If a session keeps getting restarted every cycle, the underlying agent is crashing immediately. Check:

```bash
# Watch the session directly
tmux attach -t <session-name>

# Common causes:
# - Auth expired: kimi --print -p "hello" → if 401, run kimi login
# - Missing dependencies: npm install failing in the rig
# - Disk full: df -h /home
```

### Kimi auth expires
Kimi uses OAuth device flow. Tokens expire periodically. When this happens:

```bash
# Test auth
kimi --print -p "hello"

# If 401, re-authenticate
kimi login
# Follow the browser flow to authorize

# Verify
kimi --print -p "hello"
# Should get a response
```

The automonitor will keep restarting sessions that fail due to expired auth, but they'll keep dying until auth is refreshed. This is the one manual step that can't be automated.

## Quick Start Checklist

For a new server:

- [ ] Install Gas Town: `gt` CLI available
- [ ] Install KimiGas: `kimigas` wrapper at `~/bin/kimigas` or in `$PATH`
- [ ] Authenticate Kimi: `kimi login`
- [ ] Configure agents: `gt config default-agent kimigas`
- [ ] Create a rig: `gt rig create <name>`
- [ ] Start core sessions: witness, refinery, mayor, deacon
- [ ] Add watcher crew with CLAUDE.md instructions
- [ ] Deploy automonitor script to `~/gt/settings/gt-automonitor-loop.sh`
- [ ] Start automonitor: `gt-automonitor start`
- [ ] Verify: all sessions alive, automonitor cycling, zero dead panes
