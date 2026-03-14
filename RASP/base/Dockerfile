ARG FEDORA_VERSION

# dnf install -y netcdf-devel netcdf-fortran-devel hdf5-devel zlib-devel libpng-devel jasper-devel openmpi-devel gcc-gfortran make m4 tcsh time

FROM --platform=linux/amd64 fedora:${FEDORA_VERSION}

ENV TZ=Europe/Berlin \
  BASEDIR=/root/rasp
RUN mkdir $BASEDIR
WORKDIR $BASEDIR

RUN dnf update -y && dnf install -y \
  which time findutils less vim patch diffutils \
  libpng jasper \
  netcdf netcdf-fortran \
  && dnf clean all

  RUN dnf update -y && dnf install -y \
  m4 tcsh git expect \
  gcc gcc-c++ gcc-gfortran \
  netcdf-devel netcdf-fortran-devel \
  libpng-devel jasper-devel \
  && dnf clean all
