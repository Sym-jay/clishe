# Contributing to Clishe

Thanks for considering a contribution! This covers the most common ways to help.

## Adding a new AI provider

Clishe's provider system is designed so a new backend (OpenAI, Gemini, a
different local model server, etc.) can be added without touching
`clishe_brain.py` or `clishe.sh` at all.

1. Create a new file in `providers/`, e.g. `providers/openai_provider.py`.
2. Implement the `Provider` interface from `providers/base.py`:
```python
   from .base import Provider, ProviderError

   class OpenAIProvider(Provider):
       name = "openai"

       def is_available(self) -> bool:
           # Cheap, local check only - no network call here.
           ...

       def resolve_command(self, phrase: str) -> str | None:
           # Return a shell command, or None if unclear/unsafe.
           # Raise ProviderError for real failures (network, auth, etc).
           ...

       def explain_command(self, command: str) -> str | None:
           ...
```
3. Register it in `providers/__init__.py`:
```python
   from .openai_provider import OpenAIProvider

   REGISTRY = {
       "ollama": OllamaProvider,
       "anthropic": AnthropicProvider,
       "openai": OpenAIProvider,
   }
```
4. Add tests in `tests/test_providers.py` mocking the network call, covering
   at least one success case and one failure case (see the existing
   Anthropic/Ollama tests for the pattern).
5. Mention the new provider and its config keys in the README's "Enabling
   AI features" section.

## Adding to the offline knowledge/command dictionary

`command_dictionary.json` and `error_patterns.json` (used by `explain` and
`diagnose`) can grow without any code changes — just add entries following
the existing format.

## Running tests locally

```bash
pip install pytest
python -m pytest tests/ -v
```

Please also run a quick syntax check before pushing, especially for
`clishe_brain.py` and files under `providers/`:
```bash
python -m py_compile clishe_brain.py config.py providers/*.py
```

## Pull requests

- Keep PRs focused — one change per PR is easier to review than several
  bundled together.
- Make sure `python -m pytest tests/ -v` passes before opening the PR.
- Describe *why* the change is needed, not just what it does.

## Reporting bugs or safety issues

For a general bug, open a GitHub issue with steps to reproduce.

For a safety bypass (a command running without the expected confirmation
prompt, or a destructive pattern not being caught), see `SECURITY.md`.
