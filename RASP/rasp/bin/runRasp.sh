#!/bin/bash

# check parameters
usage="$0 <region> - execute runGM on <region>, create meteograms and copy results to right location"
if [ $# -ne 1 ] ; then
    echo "ERROR: require one region to run, no/too many arguments provided"
    echo $usage;
    exit 1;
fi
REGION=$1
if [ -z "${START_DAY}" ] ; then
    START_DAY=0;
fi

regionDir="/root/rasp/${REGION}"
outDir="${regionDir}/OUT"
logDir="${regionDir}/LOG"

. ${regionDir}/rasp.site.runenvironment

runTime="$(date +%H-%M)";

# Calculate the forecast date in NZ time
# START_DAY=0 means today, START_DAY=1 means tomorrow, etc.
# Use NZ timezone (Pacific/Auckland) to get the correct forecast day
forecastDate="$(TZ='Pacific/Auckland' date -d "+${START_DAY} days" +%Y-%m-%d)";
echo "Forecast date (NZ time): ${forecastDate}"

# Create date-specific directories for this run based on forecast day
dateDir="${outDir}/${forecastDate}"
dateLogDir="${logDir}/${forecastDate}"

# Only clean up results for the forecast date (not all dates)
# This allows keeping results from different forecast dates
echo "Checking for existing results for forecast day ${forecastDate}"
if [ -d "${dateDir}" ]; then
    echo "Removing previous results for ${forecastDate} so current run is not contaminated"
    rm -rf "${dateDir}"
fi
if [ -d "${dateLogDir}" ]; then
    echo "Removing previous logs for ${forecastDate}"
    rm -rf "${dateLogDir}"
fi

# Always clean up temporary wrfout files from previous runs
rm -rf ${regionDir}/wrfout_d0*

echo "Running runGM on area ${REGION}, startDay = ${START_DAY} and hour offset = ${OFFSET_HOUR}"
runGM ${REGION}

#Generate the meteogram images
echo "Running meteogram on $(date)"
cp /root/rasp/logo.svg ${regionDir}/OUT/logo.svg
faketime '2025-12-01' ncl /root/rasp/GM/meteogram.ncl DOMAIN=\"${REGION}\" SITEDATA=\"/root/rasp/GM/sitedata.ncl\" &> ${logDir}/meteogram.out

# Generate title JSONs from data files
perl /root/rasp/bin/title2json.pl /root/rasp/${REGION}/OUT &> ${logDir}/title2json.out

# Generate geotiffs from data files
python3 /root/rasp/bin/rasp2geotiff.py /root/rasp/${REGION} &> ${logDir}/rasp2geotiff.out

# Create date-named directory and move all files (not folders) from OUT into it
mkdir -p "${dateDir}"
mkdir -p "${dateLogDir}"
echo "Moving output files to date directory: ${dateDir}"
# Move all files (not directories) from OUT to the date directory
find "${outDir}" -maxdepth 1 -type f -exec mv {} "${dateDir}/" \;

# Move some additional log files to date-specific log directory
mv ${regionDir}/wrf.out ${dateLogDir}/ 2>/dev/null || true
mv ${regionDir}/metgrid.log ${dateLogDir}/ 2>/dev/null || true
mv ${regionDir}/ungrib.log ${dateLogDir}/ 2>/dev/null || true
# Also copy current run logs to date directory
cp ${logDir}/meteogram.out ${dateLogDir}/ 2>/dev/null || true
cp ${logDir}/title2json.out ${dateLogDir}/ 2>/dev/null || true
cp ${logDir}/rasp2geotiff.out ${dateLogDir}/ 2>/dev/null || true

echo "Started running rasp for forecast ${forecastDate} at ${runTime}, ended at $(date +%Y-%m-%d_%H-%M)"

if [[ "${WEBSERVER_SEND}" == "1" ]]
then
    remoteLogDir="${WEBSERVER_RESULTSDIR}/LOG/${REGION}/${forecastDate}"
    remoteOutDir="${WEBSERVER_RESULTSDIR}/OUT/${REGION}/${forecastDate}"
    # Get ssh key from environment
    echo "${SSH_KEY}" > aufwinde_key
    chmod 0600 aufwinde_key
    # Create directories on webserver
    ssh -i aufwinde_key -o StrictHostKeychecking=no "${WEBSERVER_USER}@${WEBSERVER_HOST}" "mkdir -p ${remoteOutDir} ${remoteLogDir}"
    if [[ "$(ls -A ${dateDir})" ]]
    then
        # If there is output, sync it. Otherwise, back off and be happy with the data that is already on the webserver
        echo "Sending results to ${WEBSERVER_USER}@${WEBSERVER_HOST}:${remoteOutDir}"
        rsync -e "ssh -i aufwinde_key -o StrictHostKeychecking=no" -rlt --delete-after "${dateDir}/" "${WEBSERVER_USER}@${WEBSERVER_HOST}:${remoteOutDir}"
        if [[ "${SEND_WRFOUT}" == "1" ]]
        then
            echo "Sending wrfout files to ${WEBSERVER_USER}@${WEBSERVER_HOST}:${remoteOutDir}"
	    # wrfout files from the start of the simulation (early morning hours) are excluded, which is currently hardcoded. If you are in another timezone, adapt or remove the --exclude flag
            rsync -e "ssh -i aufwinde_key -o StrictHostKeychecking=no" -rlt --exclude='*0[3-5]:00:00' "${regionDir}"/wrfout_d02_* "${WEBSERVER_USER}@${WEBSERVER_HOST}:${remoteOutDir}"
        fi
    fi
    # Always sync contents of date-specific log directory. Do this afterwards because the copying of the results might take a while and the website is confused if the logs exist but the corresponding results do not
    echo "Sending logs to ${WEBSERVER_USER}@${WEBSERVER_HOST}:${remoteLogDir}"
    rsync -e "ssh -i aufwinde_key -o StrictHostKeychecking=no" -rlt --delete-after "${dateLogDir}/" "${WEBSERVER_USER}@${WEBSERVER_HOST}:${remoteLogDir}"
fi

if [[ "${REQUEST_DELETE}" == "1" ]]
then
    zone=$(printf ${WEBSERVER_HOST} | cut -d. -f2)
    echo "Self-destruction of $HOSTNAME in $zone"
    token=$(curl -s "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token" -H "Metadata-Flavor: Google" | perl -MJSON -0lnE '$json = decode_json $_; say $json->{access_token};')
    curl -XDELETE -H "Authorization: Bearer ${token}" https://www.googleapis.com/compute/v1/projects/aufwinde/zones/$zone/instances/$HOSTNAME
fi
