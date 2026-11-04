# Clishe shell shortcut for fish.
#
# Load it from ~/.config/fish/config.fish with:
#     clishe --init fish | source
#
# Then, at your normal prompt, type what you want in plain English and press
# Ctrl+G. Clishe swaps your words for the command, so you can read it, edit
# it, and press Enter yourself. It never runs anything on its own.
#
#   show me disk usage   [Ctrl+G]  ->  df -h
#   copy a file          [Ctrl+G]  ->  cp <file> <destination>   (cursor on <file>)
#   tar -xzvf a.tgz      [Ctrl+G]  ->  explains each flag, keeps your line
#
# Use another key with CLISHE_KEY, set before that line, e.g.
#     set -g CLISHE_KEY \eg    # Alt+G
#
# This is the fish twin of clishe-bind.zsh: same steps, but `commandline`
# reads and replaces the line instead of $BUFFER and $CURSOR.

function __clishe_print --argument-names color text
    # __clishe_print <color code> <text with literal \n line breaks>
    # The first message of a keypress starts on a fresh line below the prompt.
    if test "$__CL_PRINTED" != 1
        echo
        set -g __CL_PRINTED 1
    end
    for line in (string split '\n' -- $text)
        if isatty stdout; and test -z "$NO_COLOR"
            printf '\e[%sm%s\e[0m\n' $color $line
        else
            printf '%s\n' $line
        end
    end
end

function __clishe_ask
    # __clishe_ask <line> [--no-ai]  -> sets __CL_MODE __CL_COMMAND ...
    set -g __CL_MODE ''
    set -g __CL_COMMAND ''
    set -g __CL_NOTE ''
    set -g __CL_REASON ''
    set -g __CL_EXPLANATION ''
    set -g __CL_PROVIDER ''
    for line in (python3 $__CLISHE_BRAIN --action line --phrase $argv 2>/dev/null)
        set -l kv (string split -m 1 = -- $line)
        switch $kv[1]
            case MODE
                set -g __CL_MODE $kv[2]
            case COMMAND
                set -g __CL_COMMAND $kv[2]
            case NOTE
                set -g __CL_NOTE $kv[2]
            case REASON
                set -g __CL_REASON $kv[2]
            case EXPLANATION
                set -g __CL_EXPLANATION $kv[2]
            case PROVIDER
                set -g __CL_PROVIDER $kv[2]
        end
    end
end

# Reading and replacing the line: separate so the tests can stand in for
# `commandline`, which only works while a key is being pressed.
function __clishe_line_get
    string join \n -- (commandline)
end

function __clishe_line_set --argument-names text cursor
    commandline -r -- $text
    commandline -C -- $cursor
end

function __clishe_widget
    set -l line (__clishe_line_get)
    set -g __CL_PRINTED 0

    # Offline first: it's instant. Only say "thinking" if we need the AI.
    __clishe_ask "$line" --no-ai
    if test "$__CL_MODE" = none; and string match -qr '\S' -- "$line"
        __clishe_print 2 "clishe: thinking..."
        __clishe_ask "$line"
    end

    switch "$__CL_MODE"
        case command
            # Put the cursor on the first <placeholder>, if there is one
            # (same rule as clishe.sh, so "sort <in.txt" isn't one).
            set -l cursor (string length -- "$__CL_COMMAND")
            set -l found (string match -r --index -- '<[a-z]+( [a-z]+)*>' "$__CL_COMMAND")
            if set -q found[1]
                set cursor (math (string split ' ' -- $found[1])[1] - 1)
            end
            __clishe_line_set "$__CL_COMMAND" $cursor
            if test -n "$__CL_NOTE"
                set -l via ''
                test -n "$__CL_PROVIDER"; and set via " (via $__CL_PROVIDER)"
                __clishe_print 2 "clishe$via: $__CL_NOTE"
            end
            if test -n "$__CL_REASON"
                set -l icon ⚠
                set -q CLISHE_PLAIN; and test -n "$CLISHE_PLAIN"; and set icon Warning:
                __clishe_print 33 "$icon careful, this command:"
                for reason in (string split '\n' -- "$__CL_REASON")
                    test -n "$reason"; and __clishe_print 33 "  - $reason"
                end
            end
            if test $cursor -lt (string length -- "$__CL_COMMAND")
                __clishe_print 2 "clishe: replace the <...> parts, then press Enter."
            end
        case explain
            __clishe_print 0 "$__CL_EXPLANATION"
        case '*'
            set -l note "$__CL_NOTE"
            test -n "$note"; or set note "something went wrong. Is python3 installed?"
            __clishe_print 2 "clishe: $note"
    end

    # Draw the prompt again under whatever was printed.
    test "$__CL_PRINTED" = 1; and commandline -f repaint 2>/dev/null
end

# Tab completion: "clishe <Tab>" lists what Clishe can do, "clishe practice
# <Tab>" the lessons, "clishe explain <Tab>" your commands, "clishe check
# <Tab>" your files. Lesson names come from the file names, so pressing Tab
# never starts Python.
function __clishe_lessons
    set -l data $XDG_DATA_HOME
    test -n "$data"; or set data $HOME/.local/share
    for file in (dirname $__CLISHE_BRAIN)/lessons/*.json $data/clishe/lessons/*.json
        string replace -r '.*/(.*)\.json$' '$1' -- $file
    end
end

# __clishe_after <word>: true when the line so far is "clishe <word> ".
function __clishe_after --argument-names word
    set -l words (commandline -opc)
    test (count $words) -eq 2; and test "$words[2]" = "$word"
end

complete -c clishe -f
complete -c clishe -n 'test (count (commandline -opc)) -eq 1' \
    -a 'explain check practice progress sheet tour doctor setup'
complete -c clishe -n 'test (count (commandline -opc)) -eq 1' \
    -l list -l init -l plain -l version -l help
complete -c clishe -n '__clishe_after practice' -a '(__clishe_lessons) --list'
complete -c clishe -n '__clishe_after --init' -a 'bash zsh fish'
complete -c clishe -n '__clishe_after explain' -a '(__fish_complete_command)'
complete -c clishe -n '__clishe_after check' -F

if status is-interactive
    set -l key \cg
    set -q CLISHE_KEY; and set key $CLISHE_KEY
    bind $key __clishe_widget
    # The vi key bindings type in insert mode.
    bind -M insert $key __clishe_widget 2>/dev/null
end
