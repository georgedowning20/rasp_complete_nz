#!/bin/bash

# Enhanced RASP Wrapper Script with Debugging
# This script runs the RASP (Regional Atmospheric Soaring Prediction) forecast system

set -e
set -x  # Enable command tracing

echo "=== RASP WRAPPER DEBUG START ==="
echo "Script started at: $(date)"
echo "Script path: $0"
echo "Arguments: $@"

export BASEDIR=/root/rasp
export PATH=$PATH:$BASEDIR/bin

# Default values
REGION=${REGION:-UK12}
START_DAY=${START_DAY:-1}
OFFSET_HOUR=${OFFSET_HOUR:-0}

echo "=== CONFIGURATION ==="
echo "BASEDIR: $BASEDIR"
echo "REGION: $REGION"
echo "START_DAY: $START_DAY"
echo "OFFSET_HOUR: $OFFSET_HOUR"
echo "PATH: $PATH"

echo "=== DIRECTORY CHECK ==="
echo "Current directory: $(pwd)"
echo "BASEDIR exists: $(test -d $BASEDIR && echo 'YES' || echo 'NO')"
echo "REGION directory exists: $(test -d $BASEDIR/$REGION && echo 'YES' || echo 'NO')"

cd $BASEDIR/$REGION || {
    echo "ERROR: Cannot change to $BASEDIR/$REGION"
    echo "Available directories in $BASEDIR:"
    ls -la $BASEDIR/
    exit 1
}

echo "=== REQUIRED FILES CHECK ==="
for file in namelist.input namelist.wps; do
    if [ -f "$file" ]; then
        echo "$file: EXISTS ($(wc -l < $file) lines)"
        echo "First 5 lines of $file:"
        head -5 "$file"
    else
        echo "$file: MISSING"
    fi
done

echo "=== EXECUTABLE FILES CHECK ==="
echo "runRasp.sh exists: $(test -f $BASEDIR/bin/runRasp.sh && echo 'YES' || echo 'NO')"
if [ -f "$BASEDIR/bin/runRasp.sh" ]; then
    echo "runRasp.sh permissions: $(ls -la $BASEDIR/bin/runRasp.sh)"
    echo "runRasp.sh first 10 lines:"
    head -10 "$BASEDIR/bin/runRasp.sh"
fi

echo "=== WRF EXECUTABLES CHECK ==="
ls -la $BASEDIR/bin/*.exe 2>/dev/null || echo "No .exe files found"

echo "=== RUNNING RASP FORECAST ==="
echo "About to run: $BASEDIR/bin/runRasp.sh $REGION"

if [ -f "$BASEDIR/bin/runRasp.sh" ]; then
    echo "Executing runRasp.sh with region argument..."
    $BASEDIR/bin/runRasp.sh $REGION 2>&1 | tee /tmp/runRasp-output.log || {
        echo "ERROR: runRasp.sh failed with exit code: $?"
        echo "=== runRasp.sh OUTPUT ==="
        cat /tmp/runRasp-output.log 2>/dev/null
        echo "=== SYSTEM RESOURCES ==="
        echo "Memory usage:"
        free -h 2>/dev/null || echo "free command not available"
        echo "Disk usage:"
        df -h 2>/dev/null || echo "df command not available"
        exit 1
    }
else
    echo "ERROR: runRasp.sh not found at $BASEDIR/bin/runRasp.sh"
    echo "Available files in bin directory:"
    ls -la $BASEDIR/bin/
    exit 1
fi

echo "=== RASP WRAPPER DEBUG END ==="