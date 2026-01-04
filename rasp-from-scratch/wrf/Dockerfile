ARG FEDORA_VERSION
ARG WRF_VERSION
ARG WPS_VERSION
ARG WRF_MARCH
ARG BASE_IMAGE

FROM ${BASE_IMAGE}:fedora${FEDORA_VERSION}
ARG WRF_VERSION
ARG WPS_VERSION
ARG WRF_MARCH

# set BASEDIR early (was inherited previously but be explicit)
ENV BASEDIR=/root/rasp
RUN mkdir -p $BASEDIR

RUN dnf install -y \
    openmpi-devel \
    jasper-devel \
    libpng-devel \
    zlib-devel 

# required packages
ENV CC=gcc \
  CXX=g++ \
  FC=gfortran \
  F77=gfortran \
  NETCDF=/usr \
  NETCDF_classic=1

ENV PATH="/usr/lib64/openmpi/bin:$PATH" \
    LD_LIBRARY_PATH="/usr/lib64/openmpi/lib:$LD_LIBRARY_PATH" \
    JASPERLIB="/usr/lib64" \
    JASPERINC="/usr/include/jasper"

RUN mkdir build && cd build \
  && git clone --branch ${WRF_VERSION} --depth 1 --recurse-submodule https://github.com/wrf-model/WRF.git \
  && git clone --branch ${WPS_VERSION} --depth 1 https://github.com/wrf-model/WPS.git

COPY patch_registry.sh patch_configure_wrf.sh $BASEDIR/build/WRF/
RUN cd $BASEDIR/build/WRF \
  && ./clean -a \
  && chmod +x ./patch_configure_wrf.sh \
  && chmod +x ./patch_registry.sh \
  && sh patch_registry.sh \
  && printf "33\n1\n" | ./configure \
  && sh patch_configure_wrf.sh ${WRF_MARCH} \
  && ./compile -j 10 em_real || (echo "WRF compile failed" && exit 1)

# Must be built after WRF
COPY patch_configure_wps.sh $BASEDIR/build/WPS/

# patch_registry_wps

COPY patch_registry_wps.sh $BASEDIR/build/WPS/

# WORKDIR /root/rasp/build/WPS/arch
# RUN sed -i 's/#ARCH.*i486 i586 i686.*x86_64.*/#ARCH    Linux i486 i586 i686 x86_64 aarch64 (#serial)/g' configure.defaults && \
#     sed -i 's/#ARCH.*i486 i586 i686.*x86_64.*dmpar/#ARCH    Linux i486 i586 i686 x86_64 aarch64 (#dmpar)/g' configure.defaults

WORKDIR /root/rasp/build/WPS

RUN chmod +x ./patch_configure_wps.sh \
&& chmod +x ./patch_registry_wps.sh 

# RUN sh patch_registry_wps.sh 
  RUN printf "1\n" | ./configure 
  RUN sh patch_configure_wps.sh ${WRF_MARCH} 
  RUN ./compile || (echo "WPS compile failed" && exit 1)




# printf "1\n" | ./configure \
#   && chmod +x ./patch_configure_wps.sh \
#   && sh patch_configure_wps.sh \
#   && ./compile || (echo "WPS compile failed" && exit 1)

# RUN cd $BASEDIR/build/WPS \
#   && printf "1\n" | ./configure \
#   && sh patch_configure_wps.sh \
#   && ./compile || (echo "WPS compile failed" && exit 1)

# This first installs WRF in smpar GNU mode (option 33) and WPS in serial GNU mode (option 1).
# Some parameters in the compile configurations must be changed for the compilation to succeed.
