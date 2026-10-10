# Clishe shell shortcut for zsh.
#
# Load it from ~/.zshrc with:
#     eval "$(clishe --init zsh)"
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
#     CLISHE_KEY='^[g'    # Alt+G
#
# This is the zsh twin of clishe-bind.bash: same steps, but a ZLE widget
# that edits $BUFFER and $CURSOR instead of READLINE_LINE and READLINE_POINT.

__clishe_print() {
    # __clishe_print <color code> <text with literal \n line breaks>
    local nl=$'\n'
    local text="${2//\\n/$nl}"
    if [[ -t 1 && -z ${NO_COLOR:-} ]]; then
        print -r -- $'\e['"$1"'m'"$text"$'\e[0m'
    else
        print -r -- "$text"
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
    local line="$BUFFER" reason nl=$'\n'

    # Let our messages print above the prompt; zsh redraws it afterwards.
    zle -I 2>/dev/null

    # Offline first: it's instant. Only say "thinking" if we need the AI.
    __clishe_ask "$line" --no-ai
    if [[ $__CL_MODE == none && -n ${line//[[:space:]]/} ]]; then
        __clishe_print 2 "clishe: thinking..."
        __clishe_ask "$line"
    fi

    case "$__CL_MODE" in
        command)
            BUFFER="$__CL_COMMAND"
            # Put the cursor on the first <placeholder>, if there is one
            # (same rule as clishe.sh, so "sort <in.txt" isn't one).
            CURSOR=${#BUFFER}
            if [[ $__CL_COMMAND =~ '<[a-z]+( [a-z]+)*>' ]]; then
                CURSOR=$(( MBEGIN - 1 ))
            fi
            if [[ -n $__CL_NOTE ]]; then
                __clishe_print 2 "clishe${__CL_PROVIDER:+ (via $__CL_PROVIDER)}: $__CL_NOTE"
            fi
            if [[ -n $__CL_REASON ]]; then
                __clishe_print 33 "${CLISHE_PLAIN:+Warning:}${CLISHE_PLAIN:-⚠} careful, this command:"
                for reason in "${(@f)${__CL_REASON//\\n/$nl}}"; do
                    [[ -n $reason ]] && __clishe_print 33 "  - $reason"
                done
            fi
            if (( CURSOR < ${#BUFFER} )); then
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

# Tab completion: "clishe <Tab>" lists what Clishe can do, "clishe practice
# <Tab>" the lessons, "clishe explain <Tab>" your commands. Lesson names come
# from the file names, so pressing Tab never starts Python.
__clishe_lessons() {
    local file
    for file in ${__CLISHE_BRAIN:h}/lessons/*.json(N) \
                ${XDG_DATA_HOME:-$HOME/.local/share}/clishe/lessons/*.json(N); do
        print -r -- ${file:t:r}
    done
}

# __clishe_words <position> <first word>  -> one suggestion per line
__clishe_words() {
    if (( $1 == 2 )); then
        print -l explain check practice progress sheet tour doctor setup \
            --list --init --plain --version --help
    elif (( $1 == 3 )); then
        case $2 in
            practice) __clishe_lessons; print -- --list ;;
            --init) print -l bash zsh ;;
        esac
    fi
}

__clishe_complete() {
    local -a found
    if (( CURRENT == 3 )) && [[ ${words[2]} == explain ]]; then
        _command_names
        return
    fi
    found=(${(f)"$(__clishe_words $CURRENT ${words[2]})"})
    if (( ${#found} )); then
        compadd -a found
    else
        _files
    fi
}

if [[ -o interactive ]]; then
    zle -N __clishe_widget
    bindkey "${CLISHE_KEY:-^G}" __clishe_widget
    # Needs zsh's completion system (compinit), loaded before this file.
    (( $+functions[compdef] )) && compdef __clishe_complete clishe
fi
