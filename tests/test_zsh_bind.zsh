#!/usr/bin/env zsh
# Tests for clishe-bind.zsh, the Ctrl+G shortcut for zsh. The widget is
# called directly with BUFFER set, like zsh does on a keypress.
#
# Run with: zsh tests/test_zsh_bind.zsh

ROOT="${0:A:h:h}"
TEST_HOME="$(mktemp -d)"
trap 'rm -rf "$TEST_HOME"' EXIT
export HOME="$TEST_HOME" NO_COLOR=1
unset XDG_DATA_HOME XDG_CONFIG_HOME

pass_count=0 fail_count=0
assert_eq() {
    if [[ "$2" == "$3" ]]; then
        print "  PASS: $1"; (( pass_count++ ))
    else
        print "  FAIL: $1"; print "        expected: $2"; print "        actual:   $3"; (( fail_count++ ))
    fi
}

__CLISHE_BRAIN="$ROOT/clishe_brain.py"
source "$ROOT/clishe-bind.zsh"

print "=== zsh Ctrl+G ==="

BUFFER="show me disk usage"; CURSOR=0
__clishe_widget >/dev/null 2>&1
assert_eq "a known phrase becomes its command" "df -h" "$BUFFER"
assert_eq "cursor at the end" "5" "$CURSOR"

BUFFER="copy a file"; CURSOR=0
out=$(__clishe_widget 2>&1; print -r -- "B=$BUFFER C=$CURSOR")
assert_eq "cursor on the first placeholder" "yes" \
    "$([[ $out == *"B=cp <file> <destination> C=3"* ]] && print yes || print no)"

BUFFER="tar -xzvf a.tgz"
out=$(__clishe_widget 2>&1; print -r -- "B=$BUFFER")
assert_eq "a real command is explained, one line per part" "yes" \
    "$([[ $out == *$'\n'"  -x  extract an archive"$'\n'* && $out == *"B=tar -xzvf a.tgz" ]] && print yes || print no)"

python3() {
    print -r -- "MODE=command"; print -r -- "COMMAND=rm -rf ~"
    print -r -- 'REASON=deletes a folder\ndeletes files in your home'
}
BUFFER="wipe my home"
out=$(__clishe_widget 2>&1)
unfunction python3
assert_eq "each warning on its own line" "yes" \
    "$([[ $out == *"  - deletes a folder"$'\n'"  - deletes files in your home"* ]] && print yes || print no)"

init_out=$("$ROOT/clishe.sh" --init zsh)
assert_eq "--init zsh sources the zsh file" "yes" \
    "$([[ $init_out == *"clishe-bind.zsh"* ]] && print yes || print no)"
init_out=$(SHELL=/usr/bin/zsh "$ROOT/clishe.sh" --init)
assert_eq "--init alone picks your shell" "yes" \
    "$([[ $init_out == *"clishe-bind.zsh"* ]] && print yes || print no)"

print ""
print "=== Results: $pass_count passed, $fail_count failed ==="
(( fail_count == 0 ))
