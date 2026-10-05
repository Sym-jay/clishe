# Changelog

## Unreleased

### Added
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
- The safety check now also catches `rm *` (and `rm ./*`, `rm dir/*`),
  emptying a file with `> file` or `truncate -s 0`, commands hidden in
  `bash -c '...'`, `su -c '...'` and `eval`, scripts piped into `python3`,
  `perl`, `ruby` or `node`, and `cp`/`tee` onto a disk device.
  `rm *.log`, `echo hi > out.txt` and `>> file` are still not flagged.
- `teach` now runs the safety check before saving, as the README says, so a
  risky command needs a typed YES to be saved.
- README: "shows its work" now describes what actually asks before running.

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
