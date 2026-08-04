# Clishe

A friendly, adaptive command-line assistant that helps Linux beginners learn and navigate the shell — no memorizing man pages required.

Type what you want in plain English. Clishe figures out the command, shows you what it's about to run, and remembers it for next time.

```
You: show me disk usage
Clishe (via ollama): I think you mean: df -h
Run this? [Y/n/e=edit]: y

Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1        50G   12G   36G  25% /
```

## Why

Most CLI tools assume you already know the command you want. Clishe assumes you don't, and treats that as normal — it teaches while it helps, and gets smarter about your workflow the more you use it.

## Features

- **Natural language → shell commands.** Say what you want; Clishe resolves it to a real command.
- **Knowledge base that grows with you.** Every phrase Clishe resolves (whether from AI or manual teaching) is cached locally, so repeat requests are instant and free — no network call needed.
- **Multi-provider AI backend.** Works with a local model via [Ollama](https://ollama.com) (free, offline, private) or the Anthropic API (cloud, no local setup). Configurable priority order with automatic fallback.
- **`explain <command>`** — ask what any command does before you run it.
- **Next-command prediction** based on your own usage patterns.
- **Safety guardrails** — destructive-looking commands (`rm -rf`, `mkfs`, fork bombs, etc.) require explicit confirmation before running.
- **Zero required dependencies.** The core runs on stdlib Python 3 + bash. AI features are opt-in.

## Quickstart

### Option 1: one-line install
```bash
curl -fsSL https://raw.githubusercontent.com/Sym-jay/clishe/main/install.sh | bash
```
This clones the repo to `~/.clishe-src` and symlinks a `clishe` launcher into `~/.local/bin`. Make sure `~/.local/bin` is on your `PATH` (the installer will tell you if it isn't).

### Option 2: manual
```bash
git clone https://github.com/Sym-jay/clishe.git
cd clishe
chmod +x clishe.sh clishe_brain.py
./clishe.sh
```

## Enabling AI features (optional but recommended)

Clishe works without AI — it'll fall back to "teach me" mode for anything not in its knowledge base. To enable natural-language resolution:

### Local (Ollama) — free, offline, private
1. Install [Ollama](https://ollama.com/download)
2. Pull a small model: `ollama pull llama3.2`
3. Make sure Ollama is running (`ollama serve`, or it may already run as a background service)
4. That's it — Clishe auto-detects it via `~/.clishe_config.json`

### Cloud (Anthropic)
1. Get an API key from [console.anthropic.com](https://console.anthropic.com)
2. Edit `~/.clishe_config.json` (auto-created on first run):
   ```json
   {
     "provider_priority": ["ollama", "anthropic"],
     "anthropic": {
       "api_key": "sk-ant-...",
       "model": "claude-haiku-4-5-20251001"
     }
   }
   ```

Clishe tries providers in `provider_priority` order and falls through automatically if one is unavailable or fails. Put `ollama` first if you want to prefer free/local and only use cloud as backup.

## How it works

1. You type a phrase.
2. Clishe checks its local knowledge base (`~/.clishe_kb.json`) first — instant, free.
3. If it's not a known phrase and not a valid command already, Clishe asks the configured AI provider(s) to resolve it.
4. You approve, edit, or reject the suggestion before anything runs.
5. Successful AI resolutions are cached into the knowledge base — same phrase next time skips the AI call entirely.
6. After each command, Clishe logs it and may suggest what you'll likely want to run next, based on your own history.

## Security model

Clishe executes resolved commands via `eval`, which means it can run anything a shell command can run. Please read this before trusting it:

- Commands matching common destructive patterns (`rm -rf`, `mkfs`, `dd if=`, fork bombs, recursive `chmod`/`chown` on `/`) require typing `YES` to confirm.
- This pattern list is **not exhaustive** — it catches obvious cases, not all of them.
- AI-resolved commands are shown to you before execution; always read them, don't just hit enter.
- **Do not run Clishe as root**, and treat it as alpha software.
- If you find a way to make it execute something harmful without confirmation, please open an issue.

## Development

```bash
pip install pytest
python -m pytest tests/ -v
```

Contributions welcome — see open issues, or add a new AI provider by implementing the `Provider` interface in `providers/base.py` and registering it in `providers/__init__.py`.

## License

MIT — see [LICENSE](LICENSE).
