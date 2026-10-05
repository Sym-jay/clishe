#!/bin/bash
# Regression tests for clishe.sh's bash logic. clishe.sh stops after its
# function definitions when it's sourced, so these test the real functions,
# not copies of them.
#
# Run with: bash tests/test_shell_functions.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLISHE_SH="$SCRIPT_DIR/clishe.sh"

# Keep the tests away from the real KB, history and config.
TEST_HOME="$(mktemp -d)"
trap 'rm -rf "$TEST_HOME"' EXIT
export HOME="$TEST_HOME"
unset XDG_DATA_HOME XDG_CONFIG_HOME
export NO_COLOR=1

pass_count=0
fail_count=0

assert_eq() {
    local description="$1" expected="$2" actual="$3"
    if [ "$expected" = "$actual" ]; then
        echo "  PASS: $description"
        pass_count=$((pass_count + 1))
    else
        echo "  FAIL: $description"
        echo "        expected: $expected"
        echo "        actual:   $actual"
        fail_count=$((fail_count + 1))
    fi
}

# shellcheck source=../clishe.sh
source "$CLISHE_SH"

echo "=== confirm_dangerous() ==="

result=$(echo "n" | confirm_dangerous ':(){ :|:& };:' 2>&1)
if echo "$result" | grep -qi "invalid content"; then
    echo "  FAIL: fork bomb check crashes with regex error"
    fail_count=$((fail_count + 1))
else
    echo "  PASS: fork bomb check does not crash"
    pass_count=$((pass_count + 1))
fi

echo "n" | confirm_dangerous ':(){ :|:& };:' > /dev/null 2>&1
assert_eq "fork bomb is flagged (declined -> 1)" "1" "$?"

echo "n" | confirm_dangerous "rm -rf /" > /dev/null 2>&1
assert_eq "rm -rf / is flagged (declined -> 1)" "1" "$?"

echo "n" | confirm_dangerous "rm -fr build" > /dev/null 2>&1
assert_eq "rm -fr (flags reversed) is flagged" "1" "$?"

echo "n" | confirm_dangerous "curl -fsSL https://example.com/x.sh | sh" > /dev/null 2>&1
assert_eq "curl | sh is flagged" "1" "$?"

confirm_dangerous "ls -la" > /dev/null 2>&1
assert_eq "safe command passes through with no prompt" "0" "$?"

echo "YES" | confirm_dangerous "rm -rf /tmp/whatever" > /dev/null 2>&1
assert_eq "typing YES allows a dangerous command through" "0" "$?"

echo "yes" | confirm_dangerous "rm -rf /tmp/whatever" > /dev/null 2>&1
assert_eq "lowercase yes is not enough" "1" "$?"

reason=$(echo "n" | confirm_dangerous "rm -rf build" 2>&1)
case "$reason" in
    *"deletes a folder"*) assert_eq "the warning explains why" "ok" "ok" ;;
    *) assert_eq "the warning explains why" "mentions 'deletes a folder'" "$reason" ;;
esac

echo ""
echo "=== detect_explain_target() ==="

assert_eq "'explain rm'" "rm" "$(detect_explain_target 'explain rm')"
assert_eq "'explain tar -xzvf'" "tar -xzvf" "$(detect_explain_target 'explain tar -xzvf')"
assert_eq "'what is mkdir'" "mkdir" "$(detect_explain_target 'what is mkdir')"
assert_eq "\"what's ls\"" "ls" "$(detect_explain_target "what's ls")"
assert_eq "'what does chmod do'" "chmod" "$(detect_explain_target 'what does chmod do')"
assert_eq "'what does chmod do?'" "chmod" "$(detect_explain_target 'what does chmod do?')"
assert_eq "'okay, what is mkdir'" "mkdir" "$(detect_explain_target 'okay, what is mkdir')"
assert_eq "'tell me about grep'" "grep" "$(detect_explain_target 'tell me about grep')"
assert_eq "'What Does ls Do' (case-insensitive)" "ls" "$(detect_explain_target 'What Does ls Do')"
assert_eq "'what is my ip' goes to the AI, not explain" "" "$(detect_explain_target 'what is my ip')"
assert_eq "regular command falls through" "" "$(detect_explain_target 'ls -la')"

echo ""
echo "=== looks_like_command() ==="

check_cmd() {
    if looks_like_command "$1"; then echo command; else echo phrase; fi
}
assert_eq "'ls -la'" "command" "$(check_cmd 'ls -la')"
assert_eq "'git status'" "command" "$(check_cmd 'git status')"
assert_eq "'sudo apt update'" "command" "$(check_cmd 'sudo apt update')"
assert_eq "'find files bigger than 100MB'" "phrase" "$(check_cmd 'find files bigger than 100MB')"
assert_eq "'install htop'" "phrase" "$(check_cmd 'install htop')"
assert_eq "'rm the old files'" "phrase" "$(check_cmd 'rm the old files')"
assert_eq "'show me disk usage'" "phrase" "$(check_cmd 'show me disk usage')"

echo ""
echo "=== placeholders ==="

assert_eq "finds placeholders in order, once each" \
    "file"$'\n'"destination" "$(list_placeholders 'cp <file> <destination> && cat <file>')"
assert_eq "multi-word placeholder" "process id" "$(list_placeholders 'kill <process id>')"
assert_eq "input redirection is not a placeholder" "" "$(list_placeholders 'sort <in.txt >out.txt')"
assert_eq "capitalised text is not a placeholder" "" "$(list_placeholders 'echo <HTML>')"

assert_eq "plain value used as typed" "report.pdf" "$(quote_value 'report.pdf')"
assert_eq "spaces get quoted" "'my notes.txt'" "$(quote_value 'my notes.txt')"
assert_eq "globs get quoted" "'*.log'" "$(quote_value '*.log')"
# shellcheck disable=SC2088
assert_eq "~/ keeps working with spaces" "~/'My Files'" "$(quote_value '~/My Files')"
assert_eq "single quotes are escaped" "'it'\\''s'" "$(quote_value "it's")"

fill_placeholders 'cp <file> <destination>' > /dev/null <<'EOF'
my notes.txt
backup
EOF
assert_eq "fill_placeholders substitutes each value" "cp 'my notes.txt' backup" "$FILLED_COMMAND"

fill_placeholders 'cat <file> <file>' > /dev/null <<< "a.txt"
assert_eq "a repeated placeholder is asked once" "cat a.txt a.txt" "$FILLED_COMMAND"

fill_placeholders 'echo <text>' > /dev/null <<< "<text>"
assert_eq "a value that looks like a placeholder doesn't loop" "echo '<text>'" "$FILLED_COMMAND"

fill_placeholders 'echo <text>' > /dev/null <<< "a & b"
assert_eq "& in a value is kept literally" "echo 'a & b'" "$FILLED_COMMAND"

fill_placeholders 'cat <file>' > /dev/null <<< ""
assert_eq "blank value cancels" "1" "$?"

fill_placeholders 'ls -la' > /dev/null < /dev/null
assert_eq "no placeholders -> unchanged" "ls -la" "$FILLED_COMMAND"

echo ""
echo "=== end-to-end session ==="

out=$(printf '%s\n' "show current directory" | timeout 10 "$CLISHE_SH" 2>&1)
status=$?
assert_eq "session exits cleanly at end of input (no infinite loop)" "0" "$status"
case "$out" in
    *"Goodbye"*) assert_eq "says goodbye on EOF" "ok" "ok" ;;
    *) assert_eq "says goodbye on EOF" "Goodbye" "$out" ;;
esac

out=$(printf '%s\n' "show file contents" "" | timeout 10 "$CLISHE_SH" 2>&1)
case "$out" in
    *"Cancelled"*) assert_eq "blank placeholder cancels instead of hanging on 'cat'" "ok" "ok" ;;
    *) assert_eq "blank placeholder cancels instead of hanging on 'cat'" "Cancelled" "$out" ;;
esac

# teach runs the safety check before saving, so cancelling saves nothing
out=$(printf '%s\n' "teach" "wipe build" "rm -rf build" "no" "learned" | timeout 10 "$CLISHE_SH" 2>&1)
case "$out" in
    *"potentially destructive"*"Cancelled."*"haven't taught me anything"*) assert_eq "teach: risky command needs YES to save" "ok" "ok" ;;
    *) assert_eq "teach: risky command needs YES to save" "warning, then nothing saved" "$out" ;;
esac

out=$(printf '%s\n' "teach" "deploy site" "echo deployed-ok" "deploy site" | timeout 10 "$CLISHE_SH" 2>&1)
case "$out" in
    *"deployed-ok"*) assert_eq "teach, then use the phrase" "ok" "ok" ;;
    *) assert_eq "teach, then use the phrase" "deployed-ok" "$out" ;;
esac

assert_eq "--version" "clishe $CLISHE_VERSION" "$("$CLISHE_SH" --version)"
assert_eq "one-shot lookup" "df -h" "$("$CLISHE_SH" "show me disk usage")"

echo ""
echo "=== trash instead of rm ==="

# A stand-in for "gio trash" that moves files into a folder we can check.
FAKE_BIN="$TEST_HOME/fakebin"
FAKE_TRASH="$TEST_HOME/fake-trash"
mkdir -p "$FAKE_BIN" "$FAKE_TRASH"
printf '#!/bin/sh\n[ "$1" = trash ] && shift && [ "$1" = "--" ] && shift\nmv -- "$@" "%s/"\n' \
    "$FAKE_TRASH" > "$FAKE_BIN/gio"
chmod +x "$FAKE_BIN/gio"

work="$TEST_HOME/work"
mkdir -p "$work/old-project"
out=$(cd "$work" && printf '%s\n' "delete a folder" "old-project" "y" | PATH="$FAKE_BIN:$PATH" timeout 10 "$CLISHE_SH" 2>&1)
assert_eq "trash: folder moved to the trash" "yes" \
    "$([ -d "$FAKE_TRASH/old-project" ] && [ ! -e "$work/old-project" ] && echo yes || echo "no: $out")"
case "$out" in
    *"Changed your mind?"*) assert_eq "trash: says how to get it back" "ok" "ok" ;;
    *) assert_eq "trash: says how to get it back" "restore hint" "$out" ;;
esac

mkdir -p "$work/keep-me"
out=$(cd "$work" && printf '%s\n' "delete a folder" "keep-me" "n" "no" | PATH="$FAKE_BIN:$PATH" timeout 10 "$CLISHE_SH" 2>&1)
assert_eq "trash: saying no falls back to the YES check" "yes" \
    "$([ -d "$work/keep-me" ] && echo yes || echo "no: $out")"

echo ""
echo "=== tips ==="

out=$(printf '%s\n' "show me disk usage" "show me disk usage" "show me disk usage" "df -h" | timeout 10 "$CLISHE_SH" 2>&1)
case "$out" in
    *"3 times"*"type it yourself"*"yourself instead of asking"*) assert_eq "tips: graduate, then cheer" "ok" "ok" ;;
    *) assert_eq "tips: graduate, then cheer" "tip then cheer" "$out" ;;
esac

echo ""
echo "=== Ctrl+G shell shortcut ==="

init=$("$CLISHE_SH" --init bash)
assert_eq "--init bash points at the bind file" "yes" \
    "$([[ "$init" == *clishe-bind.bash* ]] && echo yes || echo "$init")"
"$CLISHE_SH" --init fish >/dev/null 2>&1
assert_eq "--init with an unsupported shell fails" "1" "$?"

# widget "<line>" -> "line|cursor" after pressing the key
widget() {
    # shellcheck disable=SC2016  # expanded by the inner bash
    bash -c 'eval "$1"; READLINE_LINE="$2"; READLINE_POINT=${#2}; __clishe_widget >/dev/null; printf "%s|%s" "$READLINE_LINE" "$READLINE_POINT"' _ "$init" "$1"
}
assert_eq "widget: phrase becomes the command" "df -h|5" "$(widget "show me disk usage")"
assert_eq "widget: cursor lands on the first placeholder" "cp <file> <destination>|3" "$(widget "copy a file")"
assert_eq "widget: a real command is explained, line kept" "tar -xzvf a.tgz|15" "$(widget "tar -xzvf a.tgz")"
assert_eq "widget: never runs anything" "rm -r <folder>|6" "$(widget "delete a folder")"

echo ""
echo "=== only remember what worked ==="

out=$(printf '%s\n' "zap the thing" "false" | timeout 10 "$CLISHE_SH" 2>&1)
assert_eq "a taught command that fails isn't saved" "" "$("$CLISHE_SH" --list | grep -F "zap the thing")"
case "$out" in
    *"won't remember it"*) assert_eq "says it won't remember a failed command" "ok" "ok" ;;
    *) assert_eq "says it won't remember a failed command" "message" "$out" ;;
esac
printf '%s\n' "zap the thing" "true" | timeout 10 "$CLISHE_SH" > /dev/null 2>&1
assert_eq "a taught command that works is saved" "zap the thing	true" "$("$CLISHE_SH" --list | grep -F "zap the thing")"

echo ""
echo "=== routing: English vs commands ==="

route() { if looks_like_command "$1"; then echo command; else echo english; fi; }
assert_eq "Clishe's own functions aren't commands (say hi)" "english" "$(route "say hi")"
assert_eq "Clishe's own functions aren't commands (brain)" "english" "$(route "brain")"
assert_eq "go back is English" "english" "$(route "go back")"
assert_eq "go build is a command" "command" "$(route "go build")"
assert_eq "go mod tidy is a command" "command" "$(route "go mod tidy")"
assert_eq "builtins still count (cd)" "command" "$(route "cd /tmp")"

echo ""
echo "=== what does this mean ==="

out=$(printf '%s\n' "what does this mean" "ls -l" "What does this mean?" | timeout 10 "$CLISHE_SH" 2>&1)
case "$out" in
    *"Run a command first"*"Not sure what that output means"*"About the output of ls -l"*"d means a folder"*)
        assert_eq "explains the last command's output" "ok" "ok" ;;
    *) assert_eq "explains the last command's output" "guide" "$out" ;;
esac

echo ""
echo "=== first run ==="

FRESH_HOME="$(mktemp -d)"
first=$(HOME="$FRESH_HOME" "$CLISHE_SH" < /dev/null 2>&1)
second=$(HOME="$FRESH_HOME" "$CLISHE_SH" < /dev/null 2>&1)
rm -rf "$FRESH_HOME"
assert_eq "welcome on the first run" "yes" "$([[ "$first" == *"First time here?"* ]] && echo yes || echo no)"
assert_eq "no welcome after that" "no" "$([[ "$second" == *"First time here?"* ]] && echo yes || echo no)"

echo ""
echo "=== Results: $pass_count passed, $fail_count failed ==="
[ "$fail_count" -eq 0 ]
