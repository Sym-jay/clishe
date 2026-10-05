# Clishe shell shortcut for bash.
#
# Load it from ~/.bashrc with:
#     eval "$(clishe --init bash)"
#
# Then, at your normal prompt, type what you want in plain English and press
# Ctrl+G. Clishe swaps your words for the command, so you can read it, edit
# it, and press Enter yourself. It never runs anything on its own.
#
#   show me disk usage   [Ctrl+G]  ->  df -h
#   copy a file          [Ctrl+G]  ->  cp <file> <destination>   (cursor on <file>)
#   tar -xzvf a.tgz      [Ctrl+G]  ->  explains each flag, keeps your line
#
# Use another key with CLISHE_KEY, set before the eval line, e.g.
#     CLISHE_KEY='\eg'    # Alt+G

__clishe_print() {
    # __clishe_print <color code> <text with literal \n line breaks>
    local text="${2//\\n/$'\n'}"
    if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
        printf '\033[%sm%s\033[0m\n' "$1" "$text"
    else
        printf '%s\n' "$text"
    fi
}

__clishe_ask() {
    # __clishe_ask <line> [--no-ai]  -> sets __CL_MODE __CL_COMMAND ...
    local key value
    __CL_MODE="" __CL_COMMAND="" __CL_NOTE="" __CL_REASON="" __CL_EXPLANATION="" __CL_PROVIDER=""
    while IFS='=' read -r key value; do
        case "$key" in
            MODE) __CL_MODE="$value" ;;
            COMMAND) __CL_COMMAND="$value" ;;
            NOTE) __CL_NOTE="$value" ;;
            REASON) __CL_REASON="$value" ;;
            EXPLANATION) __CL_EXPLANATION="$value" ;;
            PROVIDER) __CL_PROVIDER="$value" ;;
        esac
    done < <(python3 "$__CLISHE_BRAIN" --action line --phrase "$1" ${2:+"$2"} 2>/dev/null)
}

__clishe_widget() {
    local line="$READLINE_LINE" reason before

    # Offline first: it's instant. Only say "thinking" if we need the AI.
    __clishe_ask "$line" --no-ai
    if [ "$__CL_MODE" = "none" ] && [ -n "${line//[[:space:]]/}" ]; then
        __clishe_print 2 "clishe: thinking..."
        __clishe_ask "$line"
    fi

    case "$__CL_MODE" in
        command)
            READLINE_LINE="$__CL_COMMAND"
            # Put the cursor on the first <placeholder>, if there is one
            # (same rule as clishe.sh, so "sort <in.txt" isn't one).
            READLINE_POINT=${#READLINE_LINE}
            if [[ "$__CL_COMMAND" =~ \<[a-z]+(\ [a-z]+)*\> ]]; then
                before="${__CL_COMMAND%%"${BASH_REMATCH[0]}"*}"
                READLINE_POINT=${#before}
            fi
            if [ -n "$__CL_NOTE" ]; then
                __clishe_print 2 "clishe${__CL_PROVIDER:+ (via $__CL_PROVIDER)}: $__CL_NOTE"
            fi
            if [ -n "$__CL_REASON" ]; then
                __clishe_print 33 "⚠ careful, this command:"
                while IFS= read -r reason; do
                    [ -n "$reason" ] && __clishe_print 33 "  - $reason"
                done <<< "${__CL_REASON//\\n/$'\n'}"
            fi
            if [ "$READLINE_POINT" -lt "${#READLINE_LINE}" ]; then
                __clishe_print 2 "clishe: replace the <...> parts, then press Enter."
            fi
            ;;
        explain)
            __clishe_print 0 "$__CL_EXPLANATION"
            ;;
        *)
            __clishe_print 2 "clishe: ${__CL_NOTE:-something went wrong. Is python3 installed?}"
            ;;
    esac
}

if [[ $- == *i* ]]; then
    bind -x "\"${CLISHE_KEY:-\\C-g}\": __clishe_widget"
fi
