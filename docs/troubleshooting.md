[← Back to the README](../README.md)

# Troubleshooting

Start with **`clishe doctor`**. It checks your Python and bash, whether `clishe` is on your PATH, the Ctrl+G shortcut, your config file (including misspelled settings), the data folder, `man`, the Trash, your local AI (and whether its model is downloaded) and whether anything could be sent to the internet, and says how to fix whatever is wrong. It exits with 1 when something is actually broken. Please include its output in bug reports.

**`clishe: command not found`**
`~/.local/bin` isn't on your `PATH`. Add `export PATH="$HOME/.local/bin:$PATH"` to your `~/.bashrc`, then restart your shell.

**"No AI provider is available"**
No provider is configured or reachable. Clishe prints the underlying error under this message (for example an HTTP 401 for a bad API key). Check that `ollama serve` (or your llama.cpp / LM Studio / Jan server) is running. Clishe still works from your KB, the seed KB and teach-me mode.

**Suggestions in the wrong package manager**
Clishe reads your distro from `/etc/os-release`. If that file is missing or unusual, the AI gets no distro hint. Rejecting a suggestion saves nothing, so you can retry.

**It learned the wrong command for a phrase**
Type `teach` and enter the phrase again with the right command, or `forget <phrase>`.

**Starting over**
Delete `~/.local/share/clishe/kb.json` to forget everything you've taught it.
