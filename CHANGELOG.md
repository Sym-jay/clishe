# Changelog

## Unreleased

### Added
- **Any local model server.** Besides Ollama, Clishe now works with
  llama.cpp's `llama-server`, LM Studio, Jan, LocalAI, vLLM and anything
  else with an OpenAI-style API. It finds a running server on the usual
  ports and uses its first model, so there's usually nothing to configure.
- Linux derivatives get the right package manager: the AI is told the
  distro your system is based on (Mint and Pop!_OS get `apt`).
- Every model, local or cloud, now gets the same safety instructions
  (decline unclear or destructive requests, use `<placeholders>`). Before,
  Ollama got a shorter prompt without them.
- **Explain any installed command, offline.** When a command isn't in the
  offline dictionary, `explain` reads your system's own manual (`man`, or
  `--help` when there's no man page) and shows its one-line summary and
  the description of each flag you used. AI is asked only when there's no
  manual. Flags missing from the dictionary are filled in from the manual
  too.
- **AI suggestions are checked against the manual.** Each suggestion shows
  what your manual says about its flags, and warns about any flag the
  manual doesn't mention, which is how small local models usually go wrong.

### Changed
- **Local only by default.** The Anthropic provider is now opt-in:
  set `"enabled": true` under `"anthropic"` to use it. An
  `ANTHROPIC_API_KEY` in your environment no longer turns it on by itself.
  Existing configs with a key typed into the config file keep working.
- Model servers outside your computer and local network are refused unless
  you set `"allow_remote_ai": true`, so a typo in a host can't send your
  phrases to the internet.

## 0.4.0 (2026-10-05)

### Added
- **"What does this mean?"** After `ls -l`, `df`, `du`, `free`, `ps`,
  `uptime`, `hostname -I`, `ip`, `ss`, `lsblk`, `wc`, `git status` or
  `git log`, ask and Clishe explains the output's columns in plain English.
  Offline; the output itself is never sent anywhere. A one-time hint shows
  the first time each of these runs.
- **Install hints for your distro.** "command not found", or typing a
  well-known program that isn't installed (`htop`, `nmap`, `tree`...), now
  says the install command for your package manager (apt, dnf, pacman,
  zypper, apk), including packages with different names (`dig` is
  `dnsutils` on Ubuntu, `bind-utils` on Fedora). `python` points to
  `python3`.
- More errors explained: pip's externally-managed-environment, apt without
  sudo, "Unable to locate package", interrupted dpkg, not in sudoers,
  "not a git repository", SSH key rejected, no internet / DNS failures.
- A friendly first run: five things to try, instead of a blank prompt.
- "go back" goes to the previous folder (`cd -`).
- **Ctrl+G in your normal shell.** Add `eval "$(clishe --init bash)"` to
  `~/.bashrc`, type plain English at any prompt and press Ctrl+G: the line
  becomes the command, with the cursor on the first `<placeholder>`. On a
  real command it explains the flags instead. It never runs anything.
- **Trash instead of rm.** When you delete with `rm` and `gio` or
  `trash-cli` is installed, Clishe offers to move the files to the Trash so
  you can get them back. New `"trash"` config option: `ask` (default),
  `always`, `never`.
- **Learning tips.** After asking for the same phrase 3 (and 10) times,
  Clishe shows the command to type yourself, and cheers once when you do.
- "Did you mean...?" now matches on meaning, not just spelling: "remove a
  directory" finds "delete a folder", "how much disk is left" finds "how much
  space do i have". It uses a small synonym table, stays offline and still
  asks before running. A match never adds an action you didn't ask for, and
  on a tie the less risky command wins.
- 30 more bundled phrases (disk partitions, CPU info, open ports, zip/unzip,
  file details, services, logs and more).

### Fixed
- A taught or AI-suggested command is now saved only after it runs
  successfully. Before, a wrong command (say, a program that isn't
  installed) was saved first and then came back every time.
- Clishe's own internal functions (`say`, `warn`, `brain`...) were treated
  as commands, so typing "say hi" ran Clishe's code instead of being read
  as English.
- On machines with Go installed, "go back" ran the `go` program. `go` now
  counts as a command only before a real Go subcommand (`go build`,
  `go test`, `go mod tidy`...).
- About twice as fast: the AI provider code (and its network libraries) is
  loaded only when an AI is actually asked, and logging and next-command
  prediction are one call instead of two.
- The safety check now also catches `rm *` (and `rm ./*`, `rm dir/*`),
  emptying a file with `> file` or `truncate -s 0`, commands hidden in
  `bash -c '...'`, `su -c '...'` and `eval`, scripts piped into `python3`,
  `perl`, `ruby` or `node`, and `cp`/`tee` onto a disk device.
  `rm *.log`, `echo hi > out.txt` and `>> file` are still not flagged.
- `teach` now runs the safety check before saving, as the README says, so a
  risky command needs a typed YES to be saved.
- README: "shows its work" now describes what actually asks before running.
- The safety check now also catches moving your home folder or a system
  folder (`mv ~ /tmp/x`), a command hidden in a variable set on the same line
  (`x=rm; $x -rf /`), and code passed straight to an interpreter that deletes
  files or runs a risky shell command (`python3 -c "shutil.rmtree(...)"`,
  `perl -e 'unlink ...'`, `node -e "fs.rmSync(...)"`).
- "what's my ip" now answers offline with your local address
  (`hostname -I`). "what's my public ip" still asks the internet.
- Removed the bundled "check disk speed" phrase, which ran `sudo hdparm` on
  a disk: not something to hand a beginner without context.

## 0.3.0

### Fixed
- Piping input into Clishe (or pressing Ctrl-D) no longer spins forever at
  end of input; the session now says goodbye and exits.
- Ctrl-C stops the running command (for example `ping` or `top`) instead of
  killing Clishe.
- Seed phrases that ran incomplete commands are fixed. "show file contents"
  used to run a bare `cat`, which hung waiting for input; `kill -9`,
  `find . -name`, `tar -czvf`, `wget` and others failed with usage errors.
- Commands are printed with `printf %s` instead of `echo -e`, so a command
  containing `\n` or other escapes is shown exactly as it will run.
- A command is saved to your knowledge base only after it passes the safety
  check, so cancelling a destructive-command warning no longer leaves the
  command saved.
- The destructive-command check caught `rm -rf` but not `rm -fr`,
  `rm -r -f`, `rm --recursive`, `chmod -R 755 /`, `>/dev/sda` without a space,
  and similar variants.

### Added
- `safety.py`: a parser-based destructive-command check that explains *why*
  a command is risky. Also covers disk partitioning, `shred`,
  `find -delete`, `curl ... | sh`, fork bombs with any name,
  `git reset --hard`, `git clean -f`, force-push, shutdown/reboot and
  `crontab -r`.
- `<placeholder>` templates: commands like `cp <file> <destination>` prompt
  for each value and quote it safely. AI providers are asked to use them
  for missing values, and you can teach your own.
- "Did you mean ...?" offline fuzzy matching against known phrases, and
  forgiving matching that ignores case, punctuation and filler words.
- AI suggestions show the model's one-line explanation.
- `explain` breaks down the exact flags used (`tar -xzvf` → `-x`, `-z`,
  `-v`, `-f`), including old-style `tar xzvf` and unknown flags.
- Session commands: `help`, `learned`, `teach`, `forget <phrase>`.
- Arrow-key line editing and input history that persists across sessions.
- `clishe --version` and `clishe --list`; `NO_COLOR` support.
- When no AI provider is reachable, the underlying error is shown.
- More seed phrases (folder sizes, rename, compare files, and more).
- `LICENSE` file (the README already said MIT).

### Changed
- Data files (`kb.json`, `history.json`, input history) are written with
  owner-only permissions, and history is capped so it stays small.
- Provider JSON parsing is shared and tolerates chatter around the JSON,
  which small local models often add.
- Version numbers are unified (the banner said 1.3, `pyproject.toml` said
  0.2.0); a test keeps them in sync. Minimum Python is 3.9 everywhere.
- Shell tests now source `clishe.sh` and test the real functions instead of
  copies. CI runs shellcheck.
