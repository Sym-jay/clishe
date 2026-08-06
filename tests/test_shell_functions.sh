#!/bin/bash
# Regression tests for clishe.sh's bash-only logic: the dangerous-command
# guard and the natural-language "explain" phrase matcher. These live
# outside pytest since they test shell functions, not Python.
#
# Run with: bash tests/test_shell_functions.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLISHE_SH="$SCRIPT_DIR/clishe.sh"

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

# Colors are referenced by confirm_dangerous but our targeted `sed` extract
# below doesn't pull in clishe.sh's color definitions - define them here so
# `set -u` doesn't choke on an unbound variable.
RED='\033[0;31m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

# Pull in just the pieces we need to test, without running the main loop.
source <(sed -n '/^DANGEROUS_PATTERN=/,/^FORK_BOMB_SNIPPET=/p; /^confirm_dangerous()/,/^}/p' "$CLISHE_SH")

echo "=== confirm_dangerous() ==="

# Regression test for the bug where the fork-bomb pattern's literal {}
# caused "Invalid content of \{\}" from the bash regex engine.
result=$(echo "n" | confirm_dangerous ':(){ :|:& };:' 2>&1)
if echo "$result" | grep -qi "invalid content"; then
    echo "  FAIL: fork bomb check crashes with regex error"
    fail_count=$((fail_count + 1))
else
    echo "  PASS: fork bomb check does not crash the regex engine"
    pass_count=$((pass_count + 1))
fi

echo "n" | confirm_dangerous ':(){ :|:& };:' > /dev/null 2>&1
assert_eq "fork bomb is flagged as dangerous (declined -> exit 1)" "1" "$?"

echo "n" | confirm_dangerous "rm -rf /" > /dev/null 2>&1
assert_eq "rm -rf / is flagged as dangerous (declined -> exit 1)" "1" "$?"

confirm_dangerous "ls -la" > /dev/null 2>&1
assert_eq "safe command passes through with no prompt" "0" "$?"

echo "YES" | confirm_dangerous "rm -rf /tmp/whatever" > /dev/null 2>&1
assert_eq "typing YES allows a dangerous command through" "0" "$?"

echo ""
echo "=== explain-phrase matching ==="

# Reproduces the natural-language matcher inline (mirrors the logic in the
# main loop) so we can test it in isolation across many phrasings.
match_explain_target() {
    local user_input="$1"
    local cleaned_input explain_target=""
    cleaned_input=$(echo "$user_input" | sed -E 's/^(okay|ok|so|well|hey|um|please)[,]?[[:space:]]+//I')

    shopt -s nocasematch
    if [[ "$cleaned_input" =~ ^explain[[:space:]]+(.+)$ ]]; then
        explain_target="${BASH_REMATCH[1]}"
    elif [[ "$cleaned_input" =~ ^what[[:space:]]does[[:space:]](.+)[[:space:]]do\??$ ]]; then
        explain_target="${BASH_REMATCH[1]}"
    elif [[ "$cleaned_input" =~ ^what[[:space:]]+(is|are)[[:space:]]+(.+)\??$ ]]; then
        explain_target="${BASH_REMATCH[2]}"
    elif [[ "$cleaned_input" =~ ^what\'s[[:space:]]+(.+)\??$ ]]; then
        explain_target="${BASH_REMATCH[1]}"
    elif [[ "$cleaned_input" =~ ^tell[[:space:]]me[[:space:]]about[[:space:]](.+)$ ]]; then
        explain_target="${BASH_REMATCH[1]}"
    fi
    shopt -u nocasematch

    explain_target="${explain_target%\?}"
    explain_target="$(echo "$explain_target" | sed -E 's/^[[:space:]]+|[[:space:]]+$//g')"
    echo "$explain_target"
}

assert_eq "'explain rm'" "rm" "$(match_explain_target 'explain rm')"
assert_eq "'what is mkdir'" "mkdir" "$(match_explain_target 'what is mkdir')"
assert_eq "'what are pipes'" "pipes" "$(match_explain_target 'what are pipes')"
assert_eq "\"what's ls\"" "ls" "$(match_explain_target "what's ls")"
assert_eq "'what does chmod do'" "chmod" "$(match_explain_target 'what does chmod do')"
assert_eq "'what does chmod do?'" "chmod" "$(match_explain_target 'what does chmod do?')"
assert_eq "'okay, what is mkdir'" "mkdir" "$(match_explain_target 'okay, what is mkdir')"
assert_eq "'tell me about grep'" "grep" "$(match_explain_target 'tell me about grep')"
assert_eq "regular command falls through (no target)" "" "$(match_explain_target 'ls -la')"

echo ""
echo "=== Results: $pass_count passed, $fail_count failed ==="
[ "$fail_count" -eq 0 ]
