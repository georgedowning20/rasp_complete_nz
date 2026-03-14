#!/bin/bash

# patch.sh - Add aarch64 support to WPS configure.defaults
# This script modifies the configure.defaults file to include aarch64 architecture support

echo "WPS aarch64 Architecture Support Patch"
echo "======================================"

# Check if configure.defaults exists
if [ ! -f "arch/configure.defaults" ]; then
    echo "Error: arch/configure.defaults not found!"
    echo "Make sure you're running this script from the WPS root directory."
    exit 1
fi

# Create a backup of the original file
echo "Creating backup of configure.defaults..."
cp arch/configure.defaults arch/configure.defaults.backup

# Check if aarch64 is already present
if grep -q "aarch64" arch/configure.defaults; then
    echo "aarch64 support already present in configure.defaults"
    echo "No changes needed."
    exit 0
fi

# Find the line with "Linux i486 i586 i686, gfortran" and add aarch64 to it
echo "Adding aarch64 support to configure.defaults..."

# Use sed to modify the line
sed -i 's/#ARCH    Linux i486 i586 i686, gfortran/#ARCH    Linux i486 i586 i686 aarch64, gfortran/' arch/configure.defaults

# Verify the change was made
if grep -q "aarch64" arch/configure.defaults; then
    echo "SUCCESS: aarch64 support has been added to configure.defaults"
    echo ""
    echo "Modified line:"
    grep "aarch64" arch/configure.defaults
    echo ""
    echo "You can now run './configure' to configure WPS for aarch64 architecture."
    echo "Backup saved as: arch/configure.defaults.backup"
else
    echo "ERROR: Failed to add aarch64 support"
    echo "Restoring backup..."
    mv arch/configure.defaults.backup arch/configure.defaults
    exit 1
fi

echo ""
echo "Patch completed successfully!"
