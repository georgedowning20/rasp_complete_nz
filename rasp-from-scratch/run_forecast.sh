#!/bin/bash
# Run RASP forecasts for multiple days (today, tomorrow, day after)
# Each run uses a different START_DAY value

cd "$(dirname "$0")"

echo "=========================================="
echo "RASP Multi-Day Forecast Runner"
echo "=========================================="
echo ""

# Function to format seconds into hours:minutes:seconds
format_time() {
    local seconds=$1
    local hours=$((seconds / 3600))
    local minutes=$(((seconds % 3600) / 60))
    local secs=$((seconds % 60))
    printf "%02d:%02d:%02d" $hours $minutes $secs
}

total_start_time=$(date +%s)

for day in 0 1 2 3 4; do
    echo "=========================================="
    echo "Running forecast for START_DAY=${day}"
    echo "Started at: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "=========================================="
    
    run_start_time=$(date +%s)
    
    START_DAY=${day} docker-compose run --rm rasp
    exit_code=$?
    
    run_end_time=$(date +%s)
    run_duration=$((run_end_time - run_start_time))
    
    if [ $exit_code -eq 0 ]; then
        echo "✓ Day ${day} forecast completed successfully"
    else
        echo "✗ Day ${day} forecast failed with exit code ${exit_code}"
    fi
    
    echo "  Duration: $(format_time $run_duration)"
    
    # Clean up logs after each run to save space
    echo "  Cleaning up logs..."
    rm -rf ../results/LOG/*
    
    echo ""
done

total_end_time=$(date +%s)
total_duration=$((total_end_time - total_start_time))

echo "=========================================="
echo "All forecasts complete!"
echo "Total time: $(format_time $total_duration)"
echo "Finished at: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
