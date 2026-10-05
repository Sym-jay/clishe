# Contributing to Clishe

Thanks for considering a contribution! This covers the most common ways to help.

## Adding a new AI provider

Clishe's provider system is designed so a new backend (OpenAI, Gemini, a
different local model server, etc.) can be added without touching
`clishe_brain.py` or `clishe.sh` at all.

1. Create a new file in `providers/`, e.g. `providers/openai_provider.py`.
2. Implement the `Provider` interface from `providers/base.py`:
```python
   from .base import (Provider, ProviderError, Resolution, distro_note,
                      parse_json_reply, resolution_from_reply)

   class OpenAIProvider(Provider):
       name = "openai"

       def is_available(self) -> bool:
           # Cheap, local check only - no network call here.
           ...

       def resolve_command(self, phrase: str) -> str | None:
           # Return a shell command, or None if unclear/unsafe.
           # Raise ProviderError for real failures (network, auth, etc).
           ...

       # Optional but recommended: also return the model's one-line reason,
       # which Clishe shows under the suggestion. The default implementation
       # calls resolve_command() and leaves the explanation empty.
       def resolve_with_explanation(self, phrase: str) -> Resolution | None:
           ...

       def explain_command(self, command: str) -> str | None:
           ...
```
   `parse_json_reply()` tolerates code fences and chatter around the JSON,
   `resolution_from_reply()` turns `{"command": ..., "explanation": ...}`
   into a `Resolution`, and `distro_note()` gives the prompt text that makes
   package-manager answers fit the user's distro. Ask the model to write
   missing values as `<placeholders>` (see the existing prompts) so Clishe
   can prompt for them.
3. Register it in `providers/__init__.py`:
```python
   from .openai_provider import OpenAIProvider

   REGISTRY = {
       "ollama": OllamaProvider,
       "local": LocalProvider,
       "anthropic": AnthropicProvider,
       "openai": OpenAIProvider,
   }
```
4. Add tests in `tests/test_providers.py` mocking the network call, covering
   at least one success case and one failure case (see the existing
   Anthropic/Ollama tests for the pattern).
   A provider that sends anything over the internet must set `local = False`,
   which keeps it off until the user sets `"enabled": true` in its config.
   Clishe is local-first: please don't add cloud providers to the defaults.
5. Mention the new provider and its config keys in the README's "Enabling
   AI features" section.

## Adding to the offline knowledge/command dictionary

`command_dictionary.json` and `error_patterns.json` (used by `explain` and
`diagnose`) can grow without any code changes — just add entries following
the existing format. Short flags are listed one per key (`"-x"`, `"-z"`) so
combined flags like `-xzvf` can be explained letter by letter; subcommands
(`"status"` for git) work the same way.

## Adding seed phrases

`seed_kb.json` maps a lowercase phrase to a command. If the command needs a
value from the user, write it as a placeholder of lowercase words in angle
brackets, e.g. `"copy a file": "cp <file> <destination>"`. Never add a bare
command that needs arguments (`"cat"`), since it would hang or fail when run.
`tests/test_data_files.py` checks this.

## Improving the safety check

`safety.py` decides when Clishe asks for a typed `YES`. To cover a new
dangerous pattern, add a reason to `REASONS`, detect it in
`_check_segment()`, and add cases to both the `DANGEROUS` and `SAFE` lists
in `tests/test_safety.py`. False positives matter too: a prompt that fires
on everyday commands teaches people to type `YES` without reading.

## Running tests locally

```bash
pip install pytest
python -m pytest tests/ -v
bash tests/test_shell_functions.sh
shellcheck -S warning clishe.sh install.sh   # if you have shellcheck
```

`tests/test_shell_functions.sh` sources `clishe.sh` (which stops after its
function definitions when sourced) and tests the real bash functions, plus
a few end-to-end sessions with piped input.

## Pull requests

- Keep PRs focused — one change per PR is easier to review than several
  bundled together.
- Make sure `python -m pytest tests/ -v` passes before opening the PR.
- Describe *why* the change is needed, not just what it does.

## Reporting bugs or safety issues

For a general bug, open a GitHub issue with steps to reproduce.

For a safety bypass (a command running without the expected confirmation
prompt, or a destructive pattern not being caught), see `SECURITY.md`.
