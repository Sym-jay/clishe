#!/bin/bash
# Clishe - Natural Language Command Line Interface

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Resolve the real script location even when invoked through a symlink
# (the one-line installer symlinks clishe.sh into ~/.local/bin/clishe).
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
    DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
    SOURCE="$(readlink "$SOURCE")"
    [[ "$SOURCE" != /* ]] && SOURCE="$DIR/$SOURCE"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/clishe_brain.py"

# Commands we refuse to run without explicit typed confirmation, since a
# mis-taught phrase, a bad AI suggestion, or a corrupted KB entry could
# otherwise wipe files.
DANGEROUS_PATTERN='rm -rf|mkfs|dd if=|> /dev/sd|chmod -R 777 /|chown -R'
# Fork bombs (":(){ :|:& };:") contain literal { } which POSIX ERE treats as
# an interval-expression delimiter on some regex library versions, causing
# "Invalid content of \{\}" errors on [[ =~ ]]. Checked separately below as a
# plain substring match instead of folding it into the regex.
FORK_BOMB_SNIPPET=':(){'

# ---------- Input routing tables ----------
# Real commands that are also everyday English words. Beginners type these
# at the start of plain sentences ("find my photos", "install htop",
# "help me set up ssh"), so they only count as commands when the line also
# has flags, paths or operators.
AMBIGUOUS_WORDS=" find make install kill open cut look more watch test time mail write wait yes sort touch cat head tail who join split paste fold nice help read let set locate "

# Programs whose normal form is "<program> <subcommand> <args>", e.g.
# "git status" or "systemctl status nginx". Several plain words after these
# are still a command, not a sentence.
TOOL_COMMANDS=" git apt apt-get dnf yum pacman zypper apk systemctl journalctl docker pip pip3 npm snap flatpak brew "

# Destructive commands followed by several plain words ("rm the old files")
# read like a sentence. Let the AI interpret them instead of treating the
# words as file names.
CAUTION_WORDS=" rm mv cp shred ln chmod chown "

# Patterns for "explain"-style questions (matched case-insensitively).
RE_FILLER='^(okay|ok|so|well|hey|um|please),?[[:space:]]+(.*)$'
RE_EXPLAIN='^explain[[:space:]]+(.+)$'
RE_WHAT_DOES='^what[[:space:]]+does[[:space:]]+(.+)[[:space:]]+do\??$'
RE_WHAT_IS='^what[[:space:]]+(is|are)[[:space:]]+(.+)$'
RE_WHATS="^what's[[:space:]]+(.+)\$"
RE_TELL_ME='^tell[[:space:]]+me[[:space:]]+about[[:space:]]+(.+)$'

# Check dependencies
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 is required but was not found on this system.${NC}"
    exit 1
fi

if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo -e "${RED}Error: $PYTHON_SCRIPT not found next to this script.${NC}"
    exit 1
fi

# ---------- Functions ----------

usage() {
    cat <<'EOF'
Clishe - describe what you want in plain English.

Usage:
  clishe                    start an interactive session
  clishe explain <command>  explain what a command does, then exit
  clishe "<phrase>"         look up a phrase in your knowledge base (does not run it)
  clishe --help             show this help
EOF
}

confirm_dangerous() {
    local cmd="$1"
    if [[ "$cmd" == *"$FORK_BOMB_SNIPPET"* ]] || [[ "$cmd" =~ $DANGEROUS_PATTERN ]]; then
        echo -e "${RED}⚠ This command looks potentially destructive:${NC}"
        echo -e "  ${YELLOW}$cmd${NC}"
        read -r -p "Type YES to run it anyway, anything else to cancel: " confirm
        if [ "$confirm" != "YES" ]; then
            echo -e "${BLUE}Clishe: ${NC}Cancelled."
            return 1
        fi
    fi
    return 0
}

# Parse "KEY=value" lines from clishe_brain.py into shell variables named
# <prefix>_STATUS, <prefix>_COMMAND, <prefix>_PROVIDER, <prefix>_EXPLANATION
# and <prefix>_HINT.
#   parse_brain_output "$output" RS
parse_brain_output() {
    local output="$1"
    local prefix="$2"
    local key value k
    # Reset first, so an empty or failed call can't leave the previous
    # call's STATUS or COMMAND behind.
    for k in STATUS COMMAND PROVIDER EXPLANATION HINT; do
        printf -v "${prefix}_${k}" '%s' ""
    done
    while IFS='=' read -r key value; do
        case "$key" in
            STATUS|COMMAND|PROVIDER|EXPLANATION|HINT)
                printf -v "${prefix}_${key}" '%s' "$value" ;;
        esac
    done <<< "$output"
}

word_count() {
    local -a w
    read -r -a w <<< "$1"
    echo "${#w[@]}"
}

# Succeeds if any word after the first looks like part of a real command
# line: a flag (-x), a path (/, ., ~), a variable, a quote, or a shell
# operator. Plain English sentences don't contain these.
has_command_markers() {
    local w
    local sq="'"
    local -a words
    read -r -a words <<< "$1"
    for w in "${words[@]:1}"; do
        case "$w" in
            -*|*/*|.*|'~'*|*'$'*|*'"'*|"$sq"*|*"$sq"|*'|'*|*'>'*|*'<'*|*'&'*|*';'*)
                return 0 ;;
        esac
    done
    return 1
}

# Decide whether what the user typed is a real command line (return 0) or
# plain English that should go to the AI (return 1).
looks_like_command() {
    local input="$1"
    local -a words
    read -r -a words <<< "$input"
    local first="${words[0]}"
    local count="${#words[@]}"

    [ -z "$first" ] && return 1

    # "sudo <something>": judge what comes after sudo.
    if [ "$first" = "sudo" ] && [ "$count" -gt 1 ]; then
        case "${words[1]}" in -*) return 0 ;; esac
        looks_like_command "${words[*]:1}"
        return $?
    fi

    # The first word must be something the shell can actually run.
    case "$first" in
        */*|.*) [ -e "$first" ] || return 1 ;;
        *) command -v "$first" &> /dev/null || return 1 ;;
    esac

    # Flags, paths or operators mean the user is writing a real command.
    has_command_markers "$input" && return 0

    # "git status", "systemctl status nginx", "sudo apt update"
    [[ "$TOOL_COMMANDS" == *" $first "* ]] && return 0

    # Ambiguous English verbs: "cat notes.txt" (the file exists) is a
    # command, but "install htop" or "find files bigger than 100MB" is not.
    if [[ "$AMBIGUOUS_WORDS" == *" $first "* ]]; then
        if [ "$count" -eq 2 ] && [ -e "${words[1]}" ]; then
            return 0
        fi
        return 1
    fi

    # "rm the old files" reads like a sentence, not a file list.
    if [[ "$CAUTION_WORDS" == *" $first "* ]] && [ "$count" -ge 3 ]; then
        return 1
    fi

    return 0
}

# Print the command being asked about if the input is an explain-style
# question ("explain tar", "what does chmod do", "what's grep"), or nothing.
# Loose forms ("what is ...") only count when the target starts with a real
# command, so "what is my ip" goes to the AI instead of being "explained".
detect_explain_target() {
    local s="$1"
    local target=""
    local explicit=0

    shopt -s nocasematch
    if [[ "$s" =~ $RE_FILLER ]]; then
        s="${BASH_REMATCH[2]}"
    fi
    if [[ "$s" =~ $RE_EXPLAIN ]]; then
        target="${BASH_REMATCH[1]}"
        explicit=1
    elif [[ "$s" =~ $RE_WHAT_DOES ]]; then
        target="${BASH_REMATCH[1]}"
    elif [[ "$s" =~ $RE_WHAT_IS ]]; then
        target="${BASH_REMATCH[2]}"
    elif [[ "$s" =~ $RE_WHATS ]]; then
        target="${BASH_REMATCH[1]}"
    elif [[ "$s" =~ $RE_TELL_ME ]]; then
        target="${BASH_REMATCH[1]}"
    fi
    shopt -u nocasematch

    # Drop a trailing "?" and surrounding whitespace.
    target="${target%\?}"
    target="${target#"${target%%[![:space:]]*}"}"
    target="${target%"${target##*[![:space:]]}"}"

    if [ -n "$target" ] && [ "$explicit" -eq 0 ]; then
        local first_word="${target%% *}"
        command -v "$first_word" &> /dev/null || target=""
    fi

    printf '%s' "$target"
}

run_explain() {
    local target="$1"
    local output
    output=$(python3 "$PYTHON_SCRIPT" --action explain --command "$target" 2>/dev/null)
    parse_brain_output "$output" EX

    if [ "$EX_STATUS" = "ok" ]; then
        local decoded="${EX_EXPLANATION//\\n/$'\n'}"
        echo -e "${BLUE}Clishe (via $EX_PROVIDER): ${NC}$decoded"
        return 0
    fi

    echo -e "${YELLOW}I couldn't explain that: it isn't in my offline dictionary and no AI provider is available.${NC}"
    echo -e "${YELLOW}Set up a provider in ~/.config/clishe/config.json (see the README).${NC}"
    return 1
}

# Ask the AI to turn a phrase into a command. On approval, sets the global
# command_to_run and returns 0. Returns 1 if the user skipped.
# If no AI is available (or it declines), falls back to "teach me".
resolve_with_ai() {
    local phrase="$1"
    local approve teach_command resolve_output

    echo -e "${BLUE}Clishe: ${NC}I don't know that. Let me think..."
    resolve_output=$(python3 "$PYTHON_SCRIPT" --action resolve --phrase "$phrase" 2>/dev/null)
    parse_brain_output "$resolve_output" RS

    if [ "$RS_STATUS" = "ok" ]; then
        command_to_run="$RS_COMMAND"
        echo -e "${BLUE}Clishe (via $RS_PROVIDER): ${NC}I think you mean: ${YELLOW}$command_to_run${NC}"
        read -r -p "Run this? [Y/n/e=edit]: " approve
        if [[ "$approve" =~ ^[Nn]$ ]]; then
            echo -e "${BLUE}Clishe: ${NC}Okay, skipping. (Not saved - I'll ask again next time.)"
            return 1
        elif [[ "$approve" =~ ^[Ee] ]]; then
            read -r -e -i "$command_to_run" -p "Edit command: " command_to_run
        fi
        if [ -z "$command_to_run" ]; then
            echo -e "${BLUE}Clishe: ${NC}Nothing to run. Skipping."
            return 1
        fi
        # Only cache AFTER approval, and cache exactly what will run
        # (including any edits) - never the raw, unreviewed suggestion.
        python3 "$PYTHON_SCRIPT" --action learn --phrase "$phrase" --command "$command_to_run" > /dev/null 2>&1
        echo -e "${BLUE}Clishe: ${NC}Saved for next time - I won't need to ask the AI again for this phrase."
        return 0
    fi

    if [ "$RS_STATUS" = "declined" ]; then
        echo -e "${YELLOW}Clishe (via $RS_PROVIDER): ${NC}That looked unclear or risky, so I won't guess. Teach me instead:"
    else
        echo -e "${BLUE}Clishe: ${NC}I don't know that, and no AI provider is available right now. Teach me!"
    fi
    echo -ne "${YELLOW}What command should I run? (blank to skip) ${NC}"
    read -r teach_command

    if [ -z "$teach_command" ]; then
        echo -e "${RED}No command provided. Skipping.${NC}"
        return 1
    fi

    python3 "$PYTHON_SCRIPT" --action learn --phrase "$phrase" --command "$teach_command" > /dev/null 2>&1
    command_to_run="$teach_command"
    echo -e "${BLUE}Clishe: ${NC}Thanks! I'll remember that."
    return 0
}

# Safety check, run, show hints, log, suggest the next command.
# Sets LAST_EXIT and LAST_STDERR for the caller.
run_command() {
    local cmd="$1"
    local stderr_file diagnose_output prediction
    LAST_EXIT=0
    LAST_STDERR=""

    # Safety check before executing anything, whether it came from the KB,
    # an AI provider, or manual teaching.
    if ! confirm_dangerous "$cmd"; then
        echo ""
        return 1
    fi

    echo ""
    stderr_file=$(mktemp)
    # Redirect stderr straight to a temp file (synchronous - avoids the race
    # condition of process substitution) then replay it. This runs in this
    # shell (no pipeline), so "cd" and "export" keep working.
    eval "$cmd" 2>"$stderr_file"
    LAST_EXIT=$?
    cat "$stderr_file" >&2
    LAST_STDERR=$(cat "$stderr_file")
    rm -f "$stderr_file"
    echo ""

    if [ "$LAST_EXIT" -ne 0 ]; then
        echo -e "${RED}Command exited with code: $LAST_EXIT${NC}"
        if [ -n "$LAST_STDERR" ]; then
            diagnose_output=$(python3 "$PYTHON_SCRIPT" --action diagnose --error "$LAST_STDERR" 2>/dev/null)
            parse_brain_output "$diagnose_output" DX
            if [ "$DX_STATUS" = "ok" ]; then
                echo -e "${YELLOW}💡 ${NC}$DX_HINT"
            fi
        fi
    else
        # Only successful commands are logged, so failed guesses don't
        # pollute the next-command suggestions.
        python3 "$PYTHON_SCRIPT" --action log --command "$cmd" > /dev/null 2>&1
        prediction=$(python3 "$PYTHON_SCRIPT" --action predict --command "$cmd" 2>/dev/null)
        if [ -n "$prediction" ]; then
            echo -e "${BLUE}Clishe: ${NC}💡 You might want to run: ${YELLOW}$prediction${NC}"
        fi
    fi
    echo ""
}

# ---------- One-shot (non-interactive) mode ----------
# clishe explain "<command>"  or  clishe "<phrase>"  runs once and exits,
# so Clishe works from scripts and aliases.
if [ $# -gt 0 ]; then
    case "$1" in
        -h|--help)
            usage
            exit 0
            ;;
        explain)
            if [ $# -gt 1 ]; then
                shift
                run_explain "$*"
                exit $?
            fi
            ;;
    esac

    # Plain output (no colors) so it's safe to use inside $( ... ).
    kb_result=$(python3 "$PYTHON_SCRIPT" --action query --phrase "$*" 2>/dev/null)
    if [ -n "$kb_result" ]; then
        printf '%s\n' "$kb_result"
        exit 0
    fi
    echo "Not in the knowledge base yet. Run clishe with no arguments to ask the AI or teach it." >&2
    exit 1
fi

# ---------- Interactive session ----------

echo -e "${BLUE}╔═══════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       Welcome to Clishe v1.3          ║${NC}"
echo -e "${BLUE}║  Natural Language Command Interface   ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════╝${NC}"
echo -e "${BLUE}Say what you want in plain English. Type 'exit' to quit, or 'explain <cmd>' to learn what a command does.${NC}\n"

while true; do
    echo -ne "${GREEN}You: ${NC}"
    read -r user_input

    if [ "$user_input" = "exit" ] || [ "$user_input" = "quit" ]; then
        echo -e "${BLUE}Goodbye!${NC}"
        break
    fi

    if [ -z "$user_input" ]; then
        continue
    fi

    command_to_run=""
    input_kind=""

    # 1. Exact match in your knowledge base (or the bundled seed KB).
    #    This runs first so a phrase you taught, like "what's my ip", can't
    #    be mistaken for an explain-style question.
    kb_result=$(python3 "$PYTHON_SCRIPT" --action query --phrase "$user_input" 2>/dev/null)

    if [ -n "$kb_result" ]; then
        command_to_run="$kb_result"
        input_kind="kb"
        echo -e "${BLUE}Clishe: ${NC}I know this! Running: ${YELLOW}$command_to_run${NC}"
    else
        # 2. "explain tar", "what does chmod do", "what's grep"
        explain_target=$(detect_explain_target "$user_input")
        if [ -n "$explain_target" ]; then
            echo -e "${BLUE}Clishe: ${NC}Let me look that up..."
            run_explain "$explain_target"
            echo ""
            continue
        fi

        # 3. A real command line, or plain English for the AI?
        if looks_like_command "$user_input"; then
            command_to_run="$user_input"
            input_kind="native"
            echo -e "${BLUE}Clishe: ${NC}Executing: ${YELLOW}$command_to_run${NC}"
        else
            if resolve_with_ai "$user_input"; then
                input_kind="ai"
            else
                echo ""
                continue
            fi
        fi
    fi

    run_command "$command_to_run"

    # A "command" that failed with an error message, when the input reads
    # like a sentence, was probably plain English - offer to ask the AI.
    if [ "$input_kind" = "native" ] && [ "$LAST_EXIT" -ne 0 ] && [ -n "$LAST_STDERR" ] \
        && ! has_command_markers "$user_input" && [ "$(word_count "$user_input")" -ge 3 ]; then
        read -r -p "That didn't work. Did you mean it as plain English? Ask the AI? [y/N]: " retry
        if [[ "$retry" =~ ^[Yy]$ ]]; then
            if resolve_with_ai "$user_input"; then
                run_command "$command_to_run"
            fi
        fi
        echo ""
    fi
done
