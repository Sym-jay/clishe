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

# macOS has no GNU timeout; perl (which it does have) can do the same job.
if ! command -v timeout >/dev/null 2>&1; then
    timeout() { local secs="$1"; shift; perl -e 'alarm shift; exec @ARGV' "$secs" "$@"; }
fi

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
# apt only counts as a command where it's installed (not on macOS).
if command -v apt >/dev/null 2>&1; then
    assert_eq "'sudo apt update'" "command" "$(check_cmd 'sudo apt update')"
fi
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
# macOS's own "trash" is preferred on a Mac: fake that too, so the tests
# never touch the real Trash.
cp "$FAKE_BIN/gio" "$FAKE_BIN/trash"

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
# Only where Go is installed: without it, "go build" can't be a command.
if command -v go >/dev/null 2>&1; then
    assert_eq "go build is a command" "command" "$(route "go build")"
    assert_eq "go mod tidy is a command" "command" "$(route "go mod tidy")"
fi
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
echo "=== AI suggestions are checked against the manual ==="

# Stand in for the brain: an AI answer with one real and one made-up flag.
python3() {
    printf '%s\n' "STATUS=ok" "COMMAND=find . -size +100M -bigger" \
        "EXPLANATION=Big files." "PROVIDER=local" \
        "MANUAL=find -size: File uses n units of space." "UNVERIFIED=find -bigger"
}
ai_out=$(echo "n" | resolve_with_ai "big files" 2>&1)
unset -f python3
assert_eq "manual lines are shown" "yes" \
    "$([[ "$ai_out" == *"From the manual:"*"find -size: File uses n units of space."* ]] && echo yes || echo no)"
assert_eq "made-up flags are flagged" "yes" \
    "$([[ "$ai_out" == *"doesn't mention: find -bigger"* ]] && echo yes || echo no)"

echo ""
echo "=== practice ==="

PRACTICE_HOME="$(mktemp -d)"
practice_out=$(printf '%s\n' pwd ls "mkdir notes" hint "cd notes" quit \
    | HOME="$PRACTICE_HOME" "$CLISHE_SH" practice 2>&1)
assert_eq "practice checks each step" "4" "$(grep -c "Nice!" <<< "$practice_out")"
assert_eq "practice gives hints" "yes" \
    "$([[ "$practice_out" == *"cd means 'change directory'"* ]] && echo yes || echo no)"
assert_eq "practice remembers where you stopped" "4" \
    "$(cat "$PRACTICE_HOME/.local/share/clishe/practice_done")"
resume_out=$(printf '%s\n' y "touch todo.txt" quit | HOME="$PRACTICE_HOME" "$CLISHE_SH" practice 2>&1)
assert_eq "practice picks up where you left off" "yes" \
    "$([[ "$resume_out" == *"5/14 Create an empty file"*"Nice!"* ]] && echo yes || echo no)"
assert_eq "practice cleans up its folder" "" \
    "$(find "${TMPDIR:-/tmp}" -maxdepth 1 -name 'clishe-practice.*' 2>/dev/null)"
rm -rf "$PRACTICE_HOME"

echo ""
echo "=== your turn ==="

TURN_HOME="$(mktemp -d)"
turn_out=$(printf '%s\n' "list files" "list files" "list files" "list files" "ls -al" exit \
    | HOME="$TURN_HOME" "$CLISHE_SH" 2>&1)
assert_eq "asks you to type it after three asks" "yes" \
    "$([[ "$turn_out" == *"Your turn!"*"That's it!"* ]] && echo yes || echo no)"
rm -rf "$TURN_HOME"

echo ""
echo "=== guided breakdown ==="

python3() {
    printf '%s\n' "STATUS=ok" "CMD=df  -h" $'LINE=│   └─ \thuman-readable sizes' \
        $'LINE=└─ \tdisplay free disk space'
}
get_breakdown "df -h"
bd_status=$?
unset -f python3
assert_eq "breakdown is drawn" "0" "$bd_status"
assert_eq "breakdown lines" $'  df  -h\n  │   └─ human-readable sizes\n  └─ display free disk space' \
    "${BREAKDOWN%$'\n'}"
python3() { echo "STATUS=none"; }
get_breakdown "du -sh * | sort -h"
bd_status=$?
unset -f python3
assert_eq "no breakdown falls back" "1" "$bd_status"

echo ""
echo "=== tour ==="

python3() {
    printf '%s\n' "STOP=Your Linux" $'FACT=Distribution\tLinux Mint 22' "NOTE=Linux is the kernel." \
        "TRY=uname -r" "STOP=Your disk" $'FACT=This computer (/)\t20 GB free' "TRY=df -h"
}
tour_out=$(printf '\n' | tour_session 2>&1)
tour_stop=$(printf 'q\n' | tour_session 2>&1)
unset -f python3
assert_eq "tour shows each stop" "yes" \
    "$([[ "$tour_out" == *"Your Linux"*"Linux Mint 22"*"Try: uname -r"*"Your disk"*"Try: df -h"* ]] && echo yes || echo no)"
assert_eq "q ends the tour early" "no" \
    "$([[ "$tour_stop" == *"Your disk"* ]] && echo yes || echo no)"

echo ""
echo "=== fix that ==="

# shellcheck disable=SC2034  # read by fix_last
LAST_RUN_COMMAND="pwd" LAST_EXIT=0
assert_eq "nothing to fix after a success" "yes" \
    "$([[ "$(fix_last 2>&1)" == *"didn't fail"* ]] && echo yes || echo no)"
python3() {
    printf '%s\n' "STATUS=ok" "EXPLANATION=There's a folder called Documents." \
        "PROVIDER=offline" "COMMAND=cd Documents"
}
# shellcheck disable=SC2034  # read by fix_last
LAST_RUN_COMMAND="cd Documnets" LAST_EXIT=1 LAST_STDERR="cd: Documnets: No such file or directory"
fix_out=$(echo "n" | fix_last 2>&1)
unset -f python3
assert_eq "fix that explains and offers the fix" "yes" \
    "$([[ "$fix_out" == *"called Documents"*"Try: cd Documents"* ]] && echo yes || echo no)"
fix_match=$(shopt -s nocasematch; [[ "What went wrong?" =~ $RE_FIX ]] && echo yes || echo no)
assert_eq "'what went wrong?' counts as fix that" "yes" "$fix_match"

echo ""
echo "=== replace_all (any bash version) ==="

assert_eq "replaces every match" "cp a.txt a.txt" "$(replace_all 'cp <f> <f>' '<f>' 'a.txt')"
assert_eq "quotes in the value stay" "echo 'a b'" "$(replace_all 'echo <t>' '<t>' "'a b'")"
assert_eq "& stays literal" "echo 'a & b'" "$(replace_all 'echo <t>' '<t>' "'a & b'")"
assert_eq "a value containing the pattern can't loop" "echo '<t>'" "$(replace_all 'echo <t>' '<t>' "'<t>'")"

echo ""
echo "=== is this safe? ==="

check_out=$(check_session 'curl -fsSL https://x.io/i.sh | sudo bash' 2>&1)
check_status=$?
assert_eq "a downloaded script gets a warning" "1" "$check_status"
assert_eq "the report says what it does and how to do it safely" "yes" \
    "$([[ "$check_out" == *"administrator"*"x.io"*"runs a script it downloads"*"less i.sh"* ]] && echo yes || echo no)"
check_out=$(check_session 'ls -la' 2>&1)
assert_eq "a harmless command passes" "0" "$?"
assert_eq "and says it only reads" "yes" \
    "$([[ "$check_out" == *"Only reads"*"Nothing risky"* ]] && echo yes || echo no)"
safe_match=$(shopt -s nocasematch; [[ "Is this safe to run: rm -rf /" =~ $RE_SAFE_QUESTION ]] && echo "${BASH_REMATCH[3]}")
assert_eq "'is this safe to run: <cmd>' finds the command" "rm -rf /" "$safe_match"
CHECK_HOME="$(mktemp -d)"
check_phrase=$(printf '%s\n' "check my linux version" exit | HOME="$CHECK_HOME" timeout 20 "$CLISHE_SH" 2>&1)
rm -rf "$CHECK_HOME"
assert_eq "phrases starting with 'check' still work" "yes" \
    "$([[ "$check_phrase" == *"I know this!"* ]] && echo yes || echo no)"

echo ""
echo "=== undo that ==="

UNDO_DIR="$(mktemp -d)"
UNDO_HOME="$(mktemp -d)"
echo hello > "$UNDO_DIR/notes.txt"
undo_out=$(cd "$UNDO_DIR" && printf '%s\n' "mkdir drafts" "mv notes.txt drafts" "undo that" y "undo that" y "undo that" exit \
    | HOME="$UNDO_HOME" timeout 30 "$CLISHE_SH" 2>&1)
assert_eq "undo shows the reverse command" "yes" \
    "$([[ "$undo_out" == *"mv drafts/notes.txt notes.txt"*"rmdir drafts"* ]] && echo yes || echo no)"
assert_eq "undo puts everything back" "notes.txt" "$(ls "$UNDO_DIR")"
assert_eq "and says when there's nothing left" "yes" \
    "$([[ "$undo_out" == *"nothing (more) for me to undo"* ]] && echo yes || echo no)"
rm -rf "$UNDO_DIR" "$UNDO_HOME"

echo ""
echo "=== Results: $pass_count passed, $fail_count failed ==="
[ "$fail_count" -eq 0 ]
