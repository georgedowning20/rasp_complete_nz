#!/bin/sh

# first parameter must be the architecture name (e.g. native, generic, nocpu)
# If unsupported on this toolchain (e.g. Fedora 36 aarch64 + old binutils) we fall back to a safe baseline.
REQ_MARCH="$1"
ARCH=$(uname -m)
SAFE_MARCH_FLAG=""

# Decide on march usage
if [ -n "$REQ_MARCH" ] && [ "$REQ_MARCH" != "nocpu" ]; then
  # On aarch64 some recent GCC may emit instructions (eor3, etc.) not accepted by the assembler in older binutils
  if [ "$ARCH" = "aarch64" ] && [ "$REQ_MARCH" = "native" ]; then
    # Use a conservative baseline
    SAFE_MARCH_FLAG="-mcpu=cortex-a72"
  elif [ "$REQ_MARCH" = "generic" ]; then
    SAFE_MARCH_FLAG=""  # let GCC decide
  else
    SAFE_MARCH_FLAG="-march=$REQ_MARCH"
  fi
fi

OPTFLAGS="-O3 -ftree-vectorize -funroll-loops -ffast-math -flto=auto $SAFE_MARCH_FLAG"

awk -v optflags="$OPTFLAGS" '{
v += sub(/^FCOPTIM\s*=.*/, "FCOPTIM = " optflags);
v += sub(/-L\$\(WRF_SRC_ROOT_DIR\)\/external\/io_netcdf/, "-L$(WRF_SRC_ROOT_DIR)/external/io_netcdf -lnetcdf -lnetcdff");
print
}
END{ if(v!=2) exit 1 }' configure.wrf > newconfigure.wrf

if [ $? -eq 0 ]
then
	echo "Successfully patched configure.wrf (flags: $OPTFLAGS)"
	mv newconfigure.wrf configure.wrf
else
	echo "Could not apply all patches to configure.wrf. This is what could be done:"
	cat newconfigure.wrf
	exit 1
fi
