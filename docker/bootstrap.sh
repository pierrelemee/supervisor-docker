#!/bin/bash


## Start process 1 in the background
#/path/to/process1 &
#P1_PID=$!
#
## Start process 2 in the background
#/path/to/process2 &
#P2_PID=$!
#
## Wait for any process to exit
#wait -n
#EXIT_CODE=$?
#
## Kill the other process
#kill $P1_PID $P2_PID 2>/dev/null
#
## Exit with the status of the failed process
#exit $EXIT_CODE
SUPERVISOR_CONFIG_FILE=/etc/supervisor/conf.d/supervisord.conf

sed -i s/{{ADMIN_USERNAME}}/${ADMIN_USERNAME}/g /etc/supervisor/conf.d/supervisord.conf
sed -i s/{{ADMIN_PASSWORD}}/${ADMIN_PASSWORD}/g /etc/supervisor/conf.d/supervisord.conf

if [ -z "${SUPERVISOR_CONFIG}" ]; then
  echo "Missing environment variable SUPERVISOR_CONFIG" && exit 1
fi

if [ -f "${SUPERVISOR_CONFIG}" ]; then
  cat "${SUPERVISOR_CONFIG}" >> SUPERVISOR_CONFIG_FILE
else
  echo "${SUPERVISOR_CONFIG}" >> "${SUPERVISOR_CONFIG_FILE}"
fi

cat "${SUPERVISOR_CONFIG_FILE}"

# Launching supervisor
/usr/bin/supervisord -c "${SUPERVISOR_CONFIG_FILE}"

