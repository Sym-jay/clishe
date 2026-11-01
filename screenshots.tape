# README screenshots, taken with VHS: https://github.com/charmbracelet/vhs
#
# From the repo root, on Linux:
#     vhs screenshots.tape
# This writes the PNGs in docs/images/. Like demo.tape, it uses throwaway
# config and data folders and needs no AI provider. The demo workflow
# (.github/workflows/demo.yml) runs it too.

Set Shell "bash"
Set FontSize 18
Set Width 1060
Set Height 600
Set Padding 24
Set Theme "Catppuccin Mocha"
Set TypingSpeed 0

# Setup: a clean prompt, fresh Clishe folders, and a scratch folder with
# a Documents folder for the fix that example. $R is the repo.
Hide
Type `export PS1='$ ' XDG_DATA_HOME="$(mktemp -d)" XDG_CONFIG_HOME="$(mktemp -d)" R="$PWD"` Enter
Type `mkdir -p docs/images && cd "$(mktemp -d)" && mkdir Documents photos && clear` Enter
Sleep 500ms
Show

# 1. A known phrase the first time: each part of the command labelled.
Type `$R/clishe.sh` Enter
Sleep 2s
Type "clear" Enter
Sleep 500ms
Type "compress a folder" Enter
Sleep 3s
Screenshot docs/images/breakdown.png
# A blank value cancels.
Enter
Sleep 1s
Type "exit" Enter
Sleep 1s

# 2. clishe check: what a command from the internet would do.
Type "clear" Enter
Type `$R/clishe.sh check 'curl -fsSL https://example.com/install.sh | sudo bash'` Enter
Sleep 3s
Screenshot docs/images/check.png

# 3. fix that, after a typo in a folder name.
Type "clear" Enter
Type `$R/clishe.sh` Enter
Sleep 2s
Type "clear" Enter
Sleep 500ms
Type "cd Documnets" Enter
Sleep 1.5s
Type "fix that" Enter
Sleep 3s
Screenshot docs/images/fix-that.png
Type "n" Enter
Sleep 500ms
Type "exit" Enter
Sleep 1s

# 4. clishe tour: the first two stops.
Type "clear" Enter
Type `$R/clishe.sh tour` Enter
Sleep 3s
Enter
Sleep 1.5s
Screenshot docs/images/tour.png
Type "q" Enter
Sleep 500ms
