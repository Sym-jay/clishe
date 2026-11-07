[← Back to the README](../README.md)

# Configuration

Clishe follows the [XDG Base Directory](https://specifications.freedesktop.org/basedir-spec/latest/) layout:

| What | Default location |
|---|---|
| Config | `~/.config/clishe/config.json` (or `$XDG_CONFIG_HOME/clishe/`) |
| Your knowledge base (phrases you taught or approved) | `~/.local/share/clishe/kb.json` (or `$XDG_DATA_HOME/clishe/`) |
| Command history (for suggestions, capped) | `~/.local/share/clishe/history.json` |
| What you typed at the prompt (arrow-key recall) | `~/.local/share/clishe/input_history` |
| Phrases Clishe couldn't answer (only with `"log_unanswered": true`) | `~/.local/share/clishe/unanswered.json` |
| Seed knowledge base (bundled, read-only) | `seed_kb.json` in the install directory |

Your data files are created with owner-only permissions. Files from older versions (`~/.clishe_kb.json` and friends) are moved to the new locations automatically on first run. Set `NO_COLOR=1` to turn off colors.

**Plain mode** is for screen readers and simple terminals: words instead of symbols ("Tip:", "Warning:" instead of 💡 and ⚠), a one-line welcome instead of the box, and each command explained as a simple "part: meaning" list instead of the drawn tree. Turn it on with `clishe --plain`, with `CLISHE_PLAIN=1` in your environment (this also covers the Ctrl+G shortcut), or with `"plain": true` in the config.

The config file is created on first run with owner-only permissions (`0600`):

```json
{
  "provider_priority": ["ollama", "local", "anthropic"],
  "allow_remote_ai": false,
  "trash": "ask",
  "ollama": {
    "host": "http://localhost:11434",
    "model": "llama3.2"
  },
  "local": {
    "host": "",
    "model": ""
  },
  "anthropic": {
    "enabled": false,
    "api_key": "",
    "model": "claude-haiku-5-5"
  }
}
```

Providers are tried in `provider_priority` order. A provider that isn't running, isn't turned on, or can't be reached is skipped.

`allow_remote_ai` lets `ollama` and `local` use a model server outside your computer and local network. It's off, so a mistyped host can't send your phrases to the internet.

`learn_mode` decides when Clishe asks you to type a command yourself: `"gentle"` (the default: after you've asked for it three times), `"always"` (from the second time) or `"off"`. Add it to the config to change it.

`trash` decides what happens when you delete files with `rm` and a Trash tool (`gio` or `trash-put`) is installed: `"ask"` (the default), `"always"` (use the Trash without asking) or `"never"`.

`log_unanswered` (off by default): set it to `true` and Clishe keeps a private list of the phrases nothing offline could answer, with how often you asked. It never leaves your computer. `clishe doctor` shows the most-asked ones, so you can share any you like in an [issue](https://github.com/Sym-jay/clishe/issues) and help Clishe learn them. Delete `unanswered.json` to clear it.

`orbs` (on by default): while Clishe waits for an answer (the AI, `fix that`, `explain`), it draws a small animated orb with braille dots, so a pause doesn't look like a hang. It only shows in a normal terminal, never in plain mode, and quick answers don't flash one. Set it to `false` to turn it off. The orbs are ported from [thinking-orbs](https://www.npmjs.com/package/thinking-orbs) by Jakub Antalik (MIT, see NOTICE.md).
