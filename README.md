# jarvis-voice

Spoken briefs for Claude Code. The full reply stays on screen, and you hear what a colleague would say across the desk.

> **On screen:** 400 words, a diff and test output
> **Spoken:** "Acme, delivery policy fix. *(pause)* It's fixed and the tests pass. Want me to push it?"

Every brief starts with the project and the task, so you can tell which session is talking.

Runs on macOS, Linux and Windows. The voice (Kokoro, `bm_fable`) is local, so reply text only goes to Anthropic, through your own Claude Code sign-in.

## Requirements

- [uv](https://docs.astral.sh/uv/), `curl` and a signed-in `claude` command
- About 340 MB of disk space for the voice model

| Platform | Notes |
|---|---|
| **macOS** | Apple silicon on macOS 14 or later. Uses `afplay`, already included. |
| **Linux** | x86_64 or ARM64 with glibc 2.28 or later, so not Alpine. Needs one of `paplay`, `pw-play`, `aplay` or `ffplay`. `espeak-ng` is an optional fallback voice. |
| **Windows** | x64 or ARM64, with Claude Code running natively. Uses PowerShell, already included. |
| **WSL 2** | Follow the Linux notes. Sound needs WSLg, and only sessions inside WSL are covered. |

## Install

macOS and Linux:

```sh
uv sync
.venv/bin/jarvis install
jarvis test
```

Windows (PowerShell):

```powershell
uv sync
.venv\Scripts\jarvis install
jarvis test
```

`install` downloads the voice model, adds a Stop hook and puts `jarvis` in `~/.local/bin`. It backs up your Claude Code `settings.json` first and leaves your other hooks alone. Running sessions normally pick up the hook within a few seconds. If one stays silent, restart it.

Run `jarvis status` if you hear nothing. It shows which audio player was found.

## Use

| Command | What it does |
|---|---|
| `jarvis status` | Shows voice, mute state, hook and models |
| `jarvis mute` / `jarvis unmute` | Silences speech, including anything playing now |
| `jarvis name "Acme"` | Sets how the current repo is announced. Otherwise it uses the folder name. |
| `jarvis say "text"` | Speaks text as written |
| `jarvis test` | Runs a sample reply through the whole chain |
| `jarvis uninstall` | Removes the hook and the command |

Inside Claude Code, run these with a `!` prefix, for example `! jarvis mute`.

Change the voice with `JARVIS_VOICE` and the pace with `JARVIS_SPEED`.

## How it works

1. The Stop hook starts a background worker and returns at once, so a session is never held up. Headless `claude -p` runs stay silent.
2. Haiku names the task from your latest request and writes the brief, with no tools, settings or MCP servers loaded. Short plain replies are spoken as written and reuse the session's latest task name.
3. If the summary fails, it speaks the reply's first sentence plus any closing question, under the session's latest task name.
4. A lock means only one session speaks at a time.
5. If Kokoro fails, a system voice reads the brief instead: `say` on macOS, `espeak-ng` on Linux, or Windows' built-in speech.

The log holds timings and errors only, never reply text. Task names are kept in a `tasks` folder beside it for 7 days. `jarvis status` shows where the log is: `~/.local/share/jarvis-voice` by default, or `%LOCALAPPDATA%\\jarvis-voice` on Windows.

## Develop

```sh
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

Everything that differs by platform is in `src/jarvis_voice/system.py`. CI runs the tests on all three systems, then installs into a clean config and synthesises a real brief with `tests/smoke.py`. CI machines have no speakers, so actual sound on Linux and Windows still needs checking by a person.

## Roadmap

- Phase 2: stop speech on a new prompt, speak permission requests, occasional updates on long tasks
- Phase 3: hands-free wake word
- Phase 4: voice-note briefs over Telegram or WhatsApp
