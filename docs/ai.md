[← Back to the README](../README.md)

# AI providers (optional)

Clishe is useful without any AI. This section is for resolving phrases it hasn't seen before. Everything here runs on your own computer: free, private, and it works on a plane.

The quickest start is:

```bash
clishe setup
```

It checks your memory, suggests a model that fits (`llama3.2:1b`, `llama3.2` or `qwen2.5-coder:7b`), finds Ollama or any other local model server that's running, and can download the model and set it up for you. It also tells you whether anything could be sent to the internet (only if you turned on the cloud provider).

## Ollama

1. Install [Ollama](https://ollama.com/download).
2. Pull a small model: `ollama pull llama3.2`
3. Make sure it's running (`ollama serve`, or the background service).

Clishe detects the local server automatically. No key and no network are needed.

## llama.cpp, LM Studio, Jan, LocalAI, vLLM

Start the server with a model loaded, and Clishe finds it on the usual port (`8080`, `1234`, `1337` or `8000`) and uses the first model it lists. To pick a specific server or model, set them under `"local"`:

```json
"local": { "host": "http://localhost:8080", "model": "qwen2.5-3b-instruct" }
```

A small instruct model (1–3B parameters) is enough for turning phrases into commands, and runs on a laptop CPU.

## Optional: a cloud provider (Anthropic)

Off by default, because it sends what you type over the internet. To turn it on:

1. Get an API key from [console.anthropic.com](https://console.anthropic.com).
2. Set `"enabled": true` under `"anthropic"` in `~/.config/clishe/config.json`.
3. Provide the key as an environment variable (so no secret lives in a file):
   ```bash
   export ANTHROPIC_API_KEY="sk-ant-..."
   ```
   Or put it in the config under `anthropic.api_key`.

A key in your environment alone doesn't turn it on, so having `ANTHROPIC_API_KEY` set for another tool won't make Clishe use the cloud.

When it's on, these are sent to the API: phrases you type that aren't in your KB or seed KB, commands you ask Clishe to `explain` that aren't in the offline dictionary, a failed command and its error message when you ask `fix that` and no offline rule fits, and your distro name (for example `ubuntu`). Your knowledge base, command history and command output are never sent.
