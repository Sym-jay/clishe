#!/usr/bin/env fish
# Tests for clishe-bind.fish, the Ctrl+G shortcut for fish. `commandline`
# only works while a key is being pressed, so the two small functions that
# read and replace the line are swapped for ones that use a variable.
#
# Run with: fish tests/test_fish_bind.fish

set -g ROOT (realpath (dirname (status filename))/..)
set -g TEST_HOME (mktemp -d)
set -gx HOME $TEST_HOME
set -gx NO_COLOR 1
set -e XDG_DATA_HOME XDG_CONFIG_HOME

set -g pass_count 0
set -g fail_count 0
function assert_eq --argument-names description expected actual
    if test "$expected" = "$actual"
        echo "  PASS: $description"
        set pass_count (math $pass_count + 1)
    else
        echo "  FAIL: $description"
        echo "        expected: $expected"
        echo "        actual:   $actual"
        set fail_count (math $fail_count + 1)
    end
end

set -g __CLISHE_BRAIN $ROOT/clishe_brain.py
source $ROOT/clishe-bind.fish

function __clishe_line_get
    printf '%s' $LINE
end
function __clishe_line_set --argument-names text cursor
    set -g LINE $text
    set -g CURSOR $cursor
end
# press "<line>": what's typed, then Ctrl+G; prints the messages.
function press
    set -g LINE $argv[1]
    set -g CURSOR 0
    __clishe_widget 2>&1
end

echo "=== fish Ctrl+G ==="

press "show me disk usage" >/dev/null
assert_eq "a known phrase becomes its command" "df -h" "$LINE"
assert_eq "cursor at the end" 5 "$CURSOR"

set out (press "copy a file" | string collect)
assert_eq "a template becomes its command" "cp <file> <destination>" "$LINE"
assert_eq "cursor on the first placeholder" 3 "$CURSOR"
assert_eq "says to fill in the blanks" yes \
    (string match -q "*replace the <...> parts*" -- "$out"; and echo yes; or echo no)

set out (press "tar -xzvf a.tgz" | string collect)
assert_eq "a real command is explained, one line per part" yes \
    (string match -q "*"\n"  -x  extract an archive"\n"*" -- "$out"; and echo yes; or echo no)
assert_eq "and the line stays as typed" "tar -xzvf a.tgz" "$LINE"

function python3
    echo "MODE=command"
    echo "COMMAND=rm -rf ~"
    echo 'REASON=deletes a folder\ndeletes files in your home'
end
set out (press "wipe my home" | string collect)
functions -e python3
assert_eq "each warning on its own line" yes \
    (string match -q "*  - deletes a folder"\n"  - deletes files in your home*" -- "$out"; and echo yes; or echo no)

function python3
    echo "MODE=none"
    echo "NOTE=I don't know that one yet."
end
set out (press "something new" | string collect)
functions -e python3
assert_eq "asks the AI only after the offline try" yes \
    (string match -q "*thinking...*know that one yet*" -- "$out"; and echo yes; or echo no)
assert_eq "an unknown line stays as typed" "something new" "$LINE"

set init_out ($ROOT/clishe.sh --init fish | string collect)
assert_eq "--init fish sources the fish file" yes \
    (string match -q "*set -g __CLISHE_BRAIN*source*clishe-bind.fish*" -- "$init_out"; and echo yes; or echo no)
set init_out (env SHELL=/usr/bin/fish $ROOT/clishe.sh --init | string collect)
assert_eq "--init alone picks your shell" yes \
    (string match -q "*clishe-bind.fish*" -- "$init_out"; and echo yes; or echo no)
# The printed lines must be valid fish that loads the widget.
functions -e __clishe_widget
$ROOT/clishe.sh --init fish | source
assert_eq "its output loads the widget" yes \
    (functions -q __clishe_widget; and echo yes; or echo no)

echo ""
echo "=== Results: $pass_count passed, $fail_count failed ==="
rm -rf $TEST_HOME
test $fail_count -eq 0
