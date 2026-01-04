#!/bin/bash

# RASP Wrapper Script
# This script runs the RASP (Regional Atmospheric Soaring Prediction) forecast system

set -e

export BASEDIR=/root/rasp
export PATH=$PATH:$BASEDIR/bin

# Default values
REGION=${REGION:-UK12}
START_DAY=${START_DAY:-1}
OFFSET_HOUR=${OFFSET_HOUR:-0}

echo "Starting RASP forecast for region: $REGION"
echo "Start day: $START_DAY, Offset hour: $OFFSET_HOUR"

cd $BASEDIR/$REGION

# Check if required files exist
if [ ! -f "namelist.input" ]; then
    echo "Error: namelist.input not found in $BASEDIR/$REGION"
    exit 1
fi

if [ ! -f "namelist.wps" ]; then
    echo "Error: namelist.wps not found in $BASEDIR/$REGION"
    exit 1
fi

# Run the RASP forecast
echo "Running RASP forecast..."
if [ -f "$BASEDIR/bin/runRasp.sh" ]; then
    # runRasp.sh expects a region argument
    exec $BASEDIR/bin/runRasp.sh $REGION
else
    echo "Error: runRasp.sh not found"
    exit 1
fi