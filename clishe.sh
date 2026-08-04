#!/bin/bash
# Clishe - Natural Language Command Line Interface

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/clishe_brain.py"

# Commands we refuse to run without explicit typed confirmation, since a
# mis-taught phrase, a bad AI suggestion, or a corrupted KB entry could
# otherwise wipe files.
DANGEROUS_PATTERN='rm -rf|mkfs|dd if=|:(){ :|:& };:|> /dev/sd|chmod -R 777 /|chown -R'

# Check dependencies
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 is required but was not found on this system.${NC}"
    exit 1
fi

if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo -e "${RED}Error: $PYTHON_SCRIPT not found next to this script.${NC}"
    exit 1
fi

# Welcome message
echo -e "${BLUE}╔═══════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       Welcome to Clishe v1.2          ║${NC}"
echo -e "${BLUE}║  Natural Language Command Interface   ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════╝${NC}"
echo -e "${BLUE}Type 'exit' to quit, 'explain <cmd>' to learn what a command does${NC}\n"

confirm_dangerous() {
    local cmd="$1"
    if [[ "$cmd" =~ $DANGEROUS_PATTERN ]]; then
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

# Parse "STATUS=x" style output from clishe_brain.py into shell vars, given
# a prefix (so callers don't clobber each other's KEY vars).
#   parse_brain_output "$output" RESOLVE
# sets RESOLVE_STATUS, RESOLVE_COMMAND, RESOLVE_PROVIDER, RESOLVE_EXPLANATION
parse_brain_output() {
    local output="$1"
    local prefix="$2"
    local line key value
    while IFS='=' read -r key value; do
        case "$key" in
            STATUS) printf -v "${prefix}_STATUS" '%s' "$value" ;;
            COMMAND) printf -v "${prefix}_COMMAND" '%s' "$value" ;;
            PROVIDER) printf -v "${prefix}_PROVIDER" '%s' "$value" ;;
            EXPLANATION) printf -v "${prefix}_EXPLANATION" '%s' "$value" ;;
        esac
    done <<< "$output"
}

# Main loop
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

    # "explain <command>" / "what does <command> do" - ask a provider to
    # describe a command instead of resolving+running one.
    explain_target=""
    if [[ "$user_input" =~ ^explain[[:space:]]+(.+)$ ]]; then
        explain_target="${BASH_REMATCH[1]}"
    elif [[ "$user_input" =~ ^what[[:space:]]does[[:space:]](.+)[[:space:]]do\??$ ]]; then
        explain_target="${BASH_REMATCH[1]}"
    fi

    if [ -n "$explain_target" ]; then
        echo -e "${BLUE}Clishe: ${NC}Let me look that up..."
        explain_output=$(python3 "$PYTHON_SCRIPT" --action explain --command "$explain_target" 2>/dev/null)
        parse_brain_output "$explain_output" EX

        if [ "$EX_STATUS" = "ok" ]; then
            echo -e "${BLUE}Clishe (via $EX_PROVIDER): ${NC}$EX_EXPLANATION"
        else
            echo -e "${YELLOW}No AI provider is available to explain that right now.${NC}"
            echo -e "${YELLOW}Set up ~/.clishe_config.json to enable this (see README).${NC}"
        fi
        echo ""
        continue
    fi

    # Query the knowledge base first - free and instant
    kb_result=$(python3 "$PYTHON_SCRIPT" --action query --phrase "$user_input" 2>/dev/null)

    if [ -n "$kb_result" ]; then
        command_to_run="$kb_result"
        echo -e "${BLUE}Clishe: ${NC}I know this! Running: ${YELLOW}$command_to_run${NC}"
    else
        first_word=$(echo "$user_input" | awk '{print $1}')
        if command -v "$first_word" &> /dev/null || [ -f "$first_word" ] || [ -d "$first_word" ]; then
            command_to_run="$user_input"
            echo -e "${BLUE}Clishe: ${NC}Executing: ${YELLOW}$command_to_run${NC}"
        else
            # Not a known phrase, not a native command - ask the AI providers
            # (local first, then cloud, per ~/.clishe_config.json) before
            # falling back to manual teach-me.
            echo -e "${BLUE}Clishe: ${NC}I don't know that. Let me think..."
            resolve_output=$(python3 "$PYTHON_SCRIPT" --action resolve --phrase "$user_input" 2>/dev/null)
            parse_brain_output "$resolve_output" RS

            if [ "$RS_STATUS" = "ok" ]; then
                command_to_run="$RS_COMMAND"
                echo -e "${BLUE}Clishe (via $RS_PROVIDER): ${NC}I think you mean: ${YELLOW}$command_to_run${NC}"
                read -r -p "Run this? [Y/n/e=edit]: " approve
                if [[ "$approve" =~ ^[Nn]$ ]]; then
                    echo -e "${BLUE}Clishe: ${NC}Okay, skipping."
                    echo ""
                    continue
                elif [[ "$approve" =~ ^[Ee] ]]; then
                    read -r -e -i "$command_to_run" -p "Edit command: " command_to_run
                fi
                echo -e "${BLUE}Clishe: ${NC}Saved for next time - I won't need to ask the AI again for this phrase."
            else
                if [ "$RS_STATUS" = "declined" ]; then
                    echo -e "${YELLOW}Clishe (via $RS_PROVIDER): ${NC}That looked unclear or risky, so I won't guess. Teach me instead:"
                else
                    echo -e "${BLUE}Clishe: ${NC}I don't know that, and no AI provider is available right now. Teach me!"
                fi
                echo -ne "${YELLOW}What command should I run? (blank to skip) ${NC}"
                read -r teach_command

                if [ -z "$teach_command" ]; then
                    echo -e "${RED}No command provided. Skipping.${NC}"
                    echo ""
                    continue
                fi

                python3 "$PYTHON_SCRIPT" --action learn --phrase "$user_input" --command "$teach_command" 2>/dev/null
                command_to_run="$teach_command"
                echo -e "${BLUE}Clishe: ${NC}Thanks! I'll remember that."
            fi
        fi
    fi

    # Safety check before executing anything, whether it came from the KB,
    # an AI provider, or manual teaching.
    if ! confirm_dangerous "$command_to_run"; then
        echo ""
        continue
    fi

    echo ""
    eval "$command_to_run"
    exit_code=$?
    echo ""

    if [ $exit_code -ne 0 ]; then
        echo -e "${RED}Command exited with code: $exit_code${NC}"
    fi

    # Log the command
    python3 "$PYTHON_SCRIPT" --action log --command "$command_to_run" 2>/dev/null

    # Predict next command
    prediction=$(python3 "$PYTHON_SCRIPT" --action predict --command "$command_to_run" 2>/dev/null)

    if [ -n "$prediction" ]; then
        echo -e "${BLUE}Clishe: ${NC}💡 You might want to run: ${YELLOW}$prediction${NC}"
    fi

    echo ""
done
