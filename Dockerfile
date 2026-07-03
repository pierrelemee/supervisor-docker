FROM debian:trixie-slim

RUN apt update -y && apt upgrade -y --fix-missing && apt install -y virtualenv

COPY ./api /opt/supervisor-api
COPY docker/run.sh /opt/supervisor-api/supervisor-api
RUN chmod 777 /opt/supervisor-api/supervisor-api

# Initialize supervisor configuration
RUN cat <<EOF > /opt/supervisor-api/supervisord.conf
[supervisord]
user=root
nodaemon=true
#logfile=/dev/stdout
#pidfile=/tmp/supervisord.pid

[inet_http_server]
port = 127.0.0.1:9001
username = {{API_USERNAME}}
password = {{API_PASSWORD}}

[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface
EOF

# Setup API
WORKDIR /opt/supervisor-api

RUN virtualenv venv && . venv/bin/activate && pip install -r requirements.txt && deactivate

WORKDIR /root

EXPOSE ${SUPERVISOR_API_PORT:-8000}

# Launch the run script
CMD ["/opt/supervisor-api/supervisor-api"]