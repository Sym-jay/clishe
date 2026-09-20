# Security Policy

Clishe resolves natural-language phrases into real shell commands and executes
them via `eval`. This means it can run anything a shell command can run —
please read this before trusting it with anything important.

## What protections exist

- **Approval before execution.** Any command resolved by an AI provider is
  shown to you before it runs. You can approve it, edit it, or reject it.
  Rejected or edited suggestions are never silently cached — only the
  command you actually approved (including your edits) is saved for next
  time.
- **Destructive-pattern warnings.** Commands matching common destructive
  patterns (`rm -rf`, `mkfs`, `dd if=`, fork bombs, recursive `chmod`/`chown`
  on `/`) require you to type `YES` explicitly before they run.
- **Offline-first fallback.** If no AI provider is configured or reachable,
  Clishe never guesses — it asks you to teach it the command manually.

## What this does NOT protect against

- **The destructive-pattern list is not exhaustive.** It catches obvious,
  well-known dangerous patterns — not every way a command could cause harm
  (e.g. commands run through indirection like `sh -c "$var"`, or unusual
  argument orderings, may not be caught).
- **AI-resolved commands can still be wrong or unsafe in non-obvious ways.**
  Always read a suggested command before approving it. Treat the approval
  prompt as a real decision point, not a formality.
- **Clishe should not be run as root**, and should be treated as early-stage
  software. Running it with elevated privileges multiplies the impact of any
  gap in the above protections.
- **API keys and local model access.** If you configure a cloud provider
  (e.g. Anthropic), your typed phrases are sent to that provider's API. Keys
  are best supplied via the `ANTHROPIC_API_KEY` environment variable rather
  than stored in `~/.clishe_config.json`, though the file is created with
  restrictive (`0600`) permissions if you do store it there.

## Reporting a vulnerability or safety bypass

If you find a way to make Clishe execute something harmful **without**
triggering the confirmation prompt or the dangerous-pattern check, please
report it by opening a GitHub issue, or by [your preferred contact method —
e.g. emailing you directly, if you'd rather not disclose bypasses publicly].

Please include:
- The exact phrase or input that triggered it
- What command it resolved to
- Why it should have been caught and wasn't

We'll treat these with priority over feature requests or other bugs.
