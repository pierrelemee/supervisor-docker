#!/bin/bash

# Prepare supervisor with user configuration
SUPERVISOR_CONFIG_FILE=/etc/supervisor/conf.d/supervisord.conf

sed -i s/{{API_USERNAME}}/${SUPERVISOR_API_USERNAME}/g /etc/supervisor/conf.d/supervisord.conf
sed -i s/{{API_PASSWORD}}/${SUPERVISOR_API_PASSWORD}/g /etc/supervisor/conf.d/supervisord.conf

if [ -z "${SUPERVISOR_CONFIG}" ]; then
  echo "Missing environment variable SUPERVISOR_CONFIG" && exit 1
fi

if [ -f "${SUPERVISOR_CONFIG}" ]; then
  cat "${SUPERVISOR_CONFIG}" >> SUPERVISOR_CONFIG_FILE
else
  echo "${SUPERVISOR_CONFIG}" >> "${SUPERVISOR_CONFIG_FILE}"
fi

cat "${SUPERVISOR_CONFIG_FILE}"

# Start supervisor process in the background
/usr/bin/supervisord -c "${SUPERVISOR_CONFIG_FILE}" &
SUPERVISOR_PID=$!

# Start process 2 in the background
/usr/bin/supervisor-api &
API_PID=$!

# Wait for any of these processes to exit
wait -n
EXIT_CODE=$?

# Kill the other process
kill $SUPERVISOR_PID $API_PID 2>/dev/null

# Exit with the status of the failed process
exit $EXIT_CODE
