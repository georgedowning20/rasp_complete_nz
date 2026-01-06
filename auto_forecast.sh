#!/bin/bash

# Auto Forecast Toggle Script for macOS
# Manages automatic wake from sleep and forecast execution at 05:00
#
# Usage:
#   ./auto_forecast.sh enable   - Enable auto wake and forecast
#   ./auto_forecast.sh disable  - Disable auto wake and forecast  
#   ./auto_forecast.sh status   - Check current status

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_NAME="com.rasp.forecast"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"
LOG_FILE="$SCRIPT_DIR/auto_forecast.log"
WAKE_TIME="04:55"  # Wake 5 mins before forecast
RUN_TIME="05:00"   # Forecast run time

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}!${NC} $1"
}

create_launchagent() {
    cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${SCRIPT_DIR}/scheduled_update.sh</string>
        <string>-f</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>5</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>${LOG_FILE}</string>
    <key>StandardErrorPath</key>
    <string>${LOG_FILE}</string>
    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin</string>
    </dict>
</dict>
</plist>
EOF
}

schedule_wake() {
    # Cancel any existing RASP wake schedules
    sudo pmset repeat cancel 2>/dev/null
    
    # Schedule daily wake at 04:55
    # Format: pmset repeat wakeorpoweron MTWRFSU HH:MM:SS
    sudo pmset repeat wakeorpoweron MTWRFSU 04:55:00
    
    if [ $? -eq 0 ]; then
        print_status "Wake schedule set for 04:55 daily"
    else
        print_error "Failed to set wake schedule (requires sudo)"
        return 1
    fi
}

cancel_wake() {
    sudo pmset repeat cancel 2>/dev/null
    if [ $? -eq 0 ]; then
        print_status "Wake schedule cancelled"
    else
        print_warning "No wake schedule to cancel or requires sudo"
    fi
}

enable_auto() {
    echo "Enabling auto forecast..."
    echo ""
    
    # Create LaunchAgents directory if needed
    mkdir -p "$HOME/Library/LaunchAgents"
    
    # Create the LaunchAgent plist
    create_launchagent
    print_status "LaunchAgent created at $PLIST_PATH"
    
    # Load the LaunchAgent
    launchctl unload "$PLIST_PATH" 2>/dev/null
    launchctl load "$PLIST_PATH"
    if [ $? -eq 0 ]; then
        print_status "LaunchAgent loaded (will run at 05:00 daily)"
    else
        print_error "Failed to load LaunchAgent"
        return 1
    fi
    
    # Schedule wake from sleep
    echo ""
    echo "Setting up wake schedule (requires password)..."
    schedule_wake
    
    echo ""
    echo -e "${GREEN}Auto forecast ENABLED${NC}"
    echo "  • Mac will wake at 04:55"
    echo "  • Forecast runs at 05:00"
    echo "  • Logs: $LOG_FILE"
}

disable_auto() {
    echo "Disabling auto forecast..."
    echo ""
    
    # Unload and remove LaunchAgent
    if [ -f "$PLIST_PATH" ]; then
        launchctl unload "$PLIST_PATH" 2>/dev/null
        rm "$PLIST_PATH"
        print_status "LaunchAgent removed"
    else
        print_warning "LaunchAgent not found"
    fi
    
    # Cancel wake schedule
    echo ""
    echo "Cancelling wake schedule (requires password)..."
    cancel_wake
    
    echo ""
    echo -e "${RED}Auto forecast DISABLED${NC}"
}

show_status() {
    echo "Auto Forecast Status"
    echo "===================="
    echo ""
    
    # Check LaunchAgent
    if [ -f "$PLIST_PATH" ]; then
        echo -e "LaunchAgent: ${GREEN}Installed${NC}"
        
        # Check if loaded
        if launchctl list | grep -q "$PLIST_NAME"; then
            echo -e "LaunchAgent Status: ${GREEN}Running${NC}"
        else
            echo -e "LaunchAgent Status: ${YELLOW}Not loaded${NC}"
        fi
    else
        echo -e "LaunchAgent: ${RED}Not installed${NC}"
    fi
    
    echo ""
    
    # Check wake schedule
    echo "Wake Schedule:"
    pmset -g sched
    
    echo ""
    
    # Show last log entries if available
    if [ -f "$LOG_FILE" ]; then
        echo "Recent log (last 10 lines):"
        echo "----------------------------"
        tail -10 "$LOG_FILE"
    fi
}

# Main
case "$1" in
    enable|on)
        enable_auto
        ;;
    disable|off)
        disable_auto
        ;;
    status)
        show_status
        ;;
    *)
        echo "RASP Auto Forecast Toggle"
        echo ""
        echo "Usage: $0 {enable|disable|status}"
        echo ""
        echo "Commands:"
        echo "  enable   - Enable auto wake at 04:55 and forecast at 05:00"
        echo "  disable  - Disable auto wake and forecast"
        echo "  status   - Show current status and recent logs"
        echo ""
        echo "Current status:"
        if [ -f "$PLIST_PATH" ]; then
            echo -e "  Auto forecast is ${GREEN}ENABLED${NC}"
        else
            echo -e "  Auto forecast is ${RED}DISABLED${NC}"
        fi
        exit 1
        ;;
esac
