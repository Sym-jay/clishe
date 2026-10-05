# Demo GIF for the README, recorded with VHS: https://github.com/charmbracelet/vhs
#
# From the repo root, on Linux:
#     vhs demo.tape
# This writes demo.gif. It uses throwaway config and data folders, so your own
# knowledge base is untouched, and it needs no AI provider.

Output demo.gif

Set Shell "bash"
Set FontSize 20
Set Width 1100
Set Height 620
Set Padding 24
Set Theme "Catppuccin Mocha"
Set TypingSpeed 55ms

# Setup, not recorded: a clean prompt, fresh Clishe folders, and Ctrl+G.
Hide
Type `export PS1='$ ' XDG_DATA_HOME="$(mktemp -d)" XDG_CONFIG_HOME="$(mktemp -d)"` Enter
Type `eval "$(./clishe.sh --init bash)"` Enter
Type "clear" Enter
Show

# 1. Plain English at the normal prompt, then Ctrl+G.
Type "show me disk usage"
Sleep 800ms
Ctrl+G
Sleep 1.5s
Enter
Sleep 2.5s

# 2. A command with blanks: the cursor lands on the first one.
Type "copy a file"
Sleep 600ms
Ctrl+G
Sleep 2s
Ctrl+C
Sleep 500ms

# 3. Ctrl+G on a real command explains each flag.
Type "tar -xzvf backup.tgz"
Sleep 600ms
Ctrl+G
Sleep 3.5s
Ctrl+C
Type "clear" Enter

# 4. Inside a Clishe session: run something, then ask what the output means.
Type "./clishe.sh" Enter
Sleep 2.5s
Type "free -h" Enter
Sleep 1.5s
Type "what does this mean" Enter
Sleep 5s

# 5. The safety check, in plain English.
Type "dd if=/dev/zero of=/dev/sda" Enter
Sleep 4s
Type "no" Enter
Sleep 1.5s
Type "exit" Enter
Sleep 1s
