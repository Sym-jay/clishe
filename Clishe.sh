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
# mis-taught phrase or a corrupted KB entry could otherwise wipe files.
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

if ! python3 -c "import sklearn" &> /dev/null; then
    echo -e "${YELLOW}Warning: scikit-learn not found. Run: pip3 install scikit-learn numpy${NC}"
fi

# Welcome message
echo -e "${BLUE}╔═══════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       Welcome to Clishe v1.1          ║${NC}"
echo -e "${BLUE}║  Natural Language Command Interface   ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════╝${NC}"
echo -e "${BLUE}Type 'exit' to quit${NC}\n"

confirm_dangerous() {
    # $1 = the command about to run
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

    # Query the knowledge base
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
            echo -e "${BLUE}Clishe: ${NC}I don't know that. Teach me!"
            echo -ne "${YELLOW}What command should I run? ${NC}"
            read -r teach_command

            if [ -z "$teach_command" ]; then
                echo -e "${RED}No command provided. Skipping.${NC}"
                continue
            fi

            python3 "$PYTHON_SCRIPT" --action learn --phrase "$user_input" --command "$teach_command" 2>/dev/null
            command_to_run="$teach_command"
            echo -e "${BLUE}Clishe: ${NC}Thanks! I'll remember that. Running: ${YELLOW}$command_to_run${NC}"
        fi
    fi

    # Safety check before executing anything, whether it came from the KB,
    # was typed directly, or was just taught to us.
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
