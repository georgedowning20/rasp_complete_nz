#!/bin/bash

# Simple command execution via file system
# This script reads commands from /opt/rasp/RUN/commands.txt and executes them
# Results are written to logs and /opt/rasp/RUN/output.txt

echo "=== RASP Command Executor Started ==="
echo "Write commands to /opt/rasp/RUN/commands.txt to execute them"
echo "Output will appear in logs and /opt/rasp/RUN/output.txt"
echo "Current working directory: $(pwd)"
echo "Available RASP tools: $(ls -la /root/rasp/bin/)"

COMMAND_FILE="/opt/rasp/RUN/commands.txt"
OUTPUT_FILE="/opt/rasp/RUN/output.txt"

# Create command file if it doesn't exist
touch "$COMMAND_FILE"
touch "$OUTPUT_FILE"

echo "$(date): Command executor ready" >> "$OUTPUT_FILE"

while true; do
    if [ -s "$COMMAND_FILE" ]; then
        echo "=== Executing commands from $COMMAND_FILE ==="
        
        while IFS= read -r command; do
            if [ -n "$command" ] && [[ ! "$command" =~ ^# ]]; then
                echo "$(date): Executing: $command" | tee -a "$OUTPUT_FILE"
                
                # Execute command and capture output
                eval "$command" 2>&1 | tee -a "$OUTPUT_FILE"
                echo "$(date): Command completed with exit code: $?" | tee -a "$OUTPUT_FILE"
                echo "----------------------------------------" | tee -a "$OUTPUT_FILE"
            fi
        done < "$COMMAND_FILE"
        
        # Clear the command file after execution
        > "$COMMAND_FILE"
        echo "$(date): All commands executed, command file cleared" | tee -a "$OUTPUT_FILE"
    fi
    
    # Heartbeat
    echo "$(date): Command executor heartbeat - waiting for commands..."
    sleep 10
done