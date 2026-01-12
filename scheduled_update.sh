#!/bin/bash

# Script to wait until 05:00 local time, then run forecast and update site
# Use -f flag to run immediately without waiting

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Prevent Mac from sleeping during the entire forecast run
# caffeinate -i prevents idle sleep, -s prevents sleep when on AC power
# The & runs it in background, and we'll kill it at the end
caffeinate -i -s -w $$ &
CAFFEINATE_PID=$!
echo "Preventing sleep during forecast (caffeinate PID: $CAFFEINATE_PID)"

# Cleanup function to stop caffeinate when script exits
cleanup() {
    if [ -n "$CAFFEINATE_PID" ]; then
        kill $CAFFEINATE_PID 2>/dev/null
        echo "Sleep prevention disabled"
    fi
}
trap cleanup EXIT

# Parse command line arguments
RUN_NOW=false
while getopts "f" opt; do
    case $opt in
        f)
            RUN_NOW=true
            ;;
        *)
            echo "Usage: $0 [-f]"
            echo "  -f  Run immediately without waiting for 03:00"
            exit 1
            ;;
    esac
done

# Function to calculate seconds until 05:00
seconds_until_0500() {
    local now=$(date +%s)
    local today_0500=$(date -j -f "%Y-%m-%d %H:%M:%S" "$(date +%Y-%m-%d) 05:00:00" +%s 2>/dev/null)
    
    if [ $now -ge $today_0500 ]; then
        # 05:00 has passed today, wait until tomorrow's 05:00
        local tomorrow_0500=$(date -j -v+1d -f "%Y-%m-%d %H:%M:%S" "$(date +%Y-%m-%d) 05:00:00" +%s 2>/dev/null)
        echo $((tomorrow_0500 - now))
    else
        echo $((today_0500 - now))
    fi
}

# Calculate wait time
if [ "$RUN_NOW" = true ]; then
    echo "Running immediately (forced mode)..."
else
    wait_seconds=$(seconds_until_0500)
    wait_hours=$((wait_seconds / 3600))
    wait_minutes=$(((wait_seconds % 3600) / 60))

    echo "Current time: $(date)"
    echo "Waiting ${wait_hours} hours and ${wait_minutes} minutes until 05:00..."

    # Wait until 03:00
    sleep $wait_seconds
fi

echo "Starting at $(date)"

# Clean up results/OUT folder to avoid contamination
echo "Cleaning results/OUT folder..."
if [ -d "$SCRIPT_DIR/results/OUT" ]; then
    rm -rf "$SCRIPT_DIR/results/OUT"/*
    echo "  Removed all files from results/OUT"
else
    mkdir -p "$SCRIPT_DIR/results/OUT"
    echo "  Created results/OUT folder"
fi

# Run the forecast script
echo "Running run_forecast.sh..."
cd "$SCRIPT_DIR/rasp-from-scratch"
./run_forecast.sh

if [ $? -ne 0 ]; then
    echo "Error: run_forecast.sh failed"
    exit 1
fi

# Run the static site generator
echo "Running generate_static_site_mapbox_gl.py..."
cd "$SCRIPT_DIR"
python3 website/generate_static_site_mapbox_gl.py

if [ $? -ne 0 ]; then
    echo "Error: generate_static_site_mapbox_gl.py failed"
    exit 1
fi

# Push to git
echo "Pushing to git..."
cd "$SCRIPT_DIR"
git add .
git commit -m "update current data"
git push

if [ $? -ne 0 ]; then
    echo "Error: git push failed"
    exit 1
fi

echo "Completed successfully at $(date)"
