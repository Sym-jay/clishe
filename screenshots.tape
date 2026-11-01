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
# a Documents folder for the fix that example. Each Screenshot is followed
# by a pause, so the next keys don't land in the picture.
Hide
Type `export PS1='$ ' XDG_DATA_HOME="$(mktemp -d)" XDG_CONFIG_HOME="$(mktemp -d)"` Enter
Type `alias clishe="$PWD/clishe.sh" && mkdir -p docs/images` Enter
Type `cd "$(mktemp -d)" && mkdir Documents photos && clear` Enter
Sleep 500ms
Show

# 1. A known phrase the first time: each part of the command labelled,
# then the blanks filled in.
Type "clishe" Enter
Sleep 2s
Type "clear" Enter
Sleep 500ms
Type "compress a folder" Enter
Sleep 2s
Type "photos-backup" Enter
Sleep 500ms
Type "photos" Enter
Sleep 2s
Screenshot docs/images/breakdown.png
Sleep 1s
Type "exit" Enter
Sleep 1s

# 2. clishe check: what a command from the internet would do.
Type "clear" Enter
Type `clishe check 'curl -fsSL https://example.com/install.sh | sudo bash'` Enter
Sleep 3s
Screenshot docs/images/check.png
Sleep 1s

# 3. fix that, after a typo in a folder name.
Type "clear" Enter
Type "clishe" Enter
Sleep 2s
Type "clear" Enter
Sleep 500ms
Type "cd Documnets" Enter
Sleep 1.5s
Type "fix that" Enter
Sleep 3s
Screenshot docs/images/fix-that.png
Sleep 1s
Type "n" Enter
Sleep 500ms
Type "exit" Enter
Sleep 1s

# 4. clishe tour: the first two stops.
Type "clear" Enter
Type "clishe tour" Enter
Sleep 3s
Enter
Sleep 1.5s
Screenshot docs/images/tour.png
Sleep 1s
Type "q" Enter
Sleep 500ms
