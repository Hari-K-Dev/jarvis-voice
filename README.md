# jarvis-voice

Spoken briefs for Claude Code. The full reply stays on screen, and you hear what a colleague would say across the desk.

> **On screen:** 400 words, a diff and test output
> **Spoken:** "Psynapse, delivery policy fix. *(pause)* It's fixed and the tests pass. Want me to push it?"

Every brief starts with the project and the task, so you can tell which session is talking.

Runs on macOS. The voice (Kokoro, `bm_fable`) is local, so reply text only goes to Anthropic, through your own Claude Code sign-in.

## Install

Needs [uv](https://docs.astral.sh/uv/) and a signed-in `claude` command.

```sh
uv sync
.venv/bin/jarvis install   # downloads the 340 MB voice model, adds a Stop hook, links `jarvis`
jarvis test
```

`install` backs up `~/.claude/settings.json` first and leaves your other hooks alone. New Claude Code sessions pick up the hook.

## Use

| Command | What it does |
|---|---|
| `jarvis status` | Shows voice, mute state, hook and models |
| `jarvis mute` / `jarvis unmute` | Silences speech, including anything playing now |
| `jarvis name "Psynapse"` | Sets how the current repo is announced. Otherwise it uses the folder name. |
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
5. If Kokoro fails, the macOS voice reads the brief instead.

The log at `~/.local/share/jarvis-voice/jarvis.log` holds timings and errors only, never reply text. Task names are kept in `tasks/` in the same private folder for 7 days.

## Develop

```sh
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

## Roadmap

- Phase 2: stop speech on a new prompt, speak permission requests, occasional updates on long tasks
- Phase 3: hands-free wake word
- Phase 4: voice-note briefs over Telegram or WhatsApp
