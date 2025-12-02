#!/bin/bash

# Clishe - Natural Language Command Line Interface
# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

PYTHON_SCRIPT="clishe_brain.py"

# Check if Python script exists
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo -e "${RED}Error: $PYTHON_SCRIPT not found in current directory${NC}"
    exit 1
fi

# Welcome message
echo -e "${BLUE}╔═══════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       Welcome to Clishe v1.0          ║${NC}"
echo -e "${BLUE}║  Natural Language Command Interface   ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════╝${NC}"
echo -e "${BLUE}Type 'exit' to quit${NC}\n"

# Main loop
while true; do
    # Read user input
    echo -ne "${GREEN}You: ${NC}"
    read -r user_input
    
    # Check for exit command
    if [ "$user_input" = "exit" ] || [ "$user_input" = "quit" ]; then
        echo -e "${BLUE}Goodbye!${NC}"
        break
    fi
    
    # Skip empty input
    if [ -z "$user_input" ]; then
        continue
    fi
    
    # Query the knowledge base
    kb_result=$(python3 "$PYTHON_SCRIPT" --action query --phrase "$user_input" 2>/dev/null)
    
    if [ -n "$kb_result" ]; then
        # Command found in KB
        command_to_run="$kb_result"
        echo -e "${BLUE}Clishe: ${NC}I know this! Running: ${YELLOW}$command_to_run${NC}"
    else
        # Check if input is a valid command
        first_word=$(echo "$user_input" | awk '{print $1}')
        if command -v "$first_word" &> /dev/null || [ -f "$first_word" ] || [ -d "$first_word" ]; then
            # It's a native command
            command_to_run="$user_input"
            echo -e "${BLUE}Clishe: ${NC}Executing: ${YELLOW}$command_to_run${NC}"
        else
            # Unknown phrase - teach it
            echo -e "${BLUE}Clishe: ${NC}I don't know that. Teach me!"
            echo -ne "${YELLOW}What command should I run? ${NC}"
            read -r teach_command
            
            if [ -z "$teach_command" ]; then
                echo -e "${RED}No command provided. Skipping.${NC}"
                continue
            fi
            
            # Learn the mapping
            python3 "$PYTHON_SCRIPT" --action learn --phrase "$user_input" --command "$teach_command" 2>/dev/null
            command_to_run="$teach_command"
            echo -e "${BLUE}Clishe: ${NC}Thanks! I'll remember that. Running: ${YELLOW}$command_to_run${NC}"
        fi
    fi
    
    # Execute the command
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