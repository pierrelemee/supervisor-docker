FROM debian:trixie-slim

RUN apt update -y && apt upgrade -y --fix-missing && apt install -y supervisor virtualenv

# Initialize supervisor configuration
RUN cat <<EOF > /etc/supervisor/conf.d/supervisord.conf
[supervisord]
user=root
nodaemon=true
#logfile=/dev/stdout
#pidfile=/tmp/supervisord.pid

[inet_http_server]
port = 127.0.0.1:9001
username = {{ADMIN_USERNAME}}
password = {{ADMIN_PASSWORD}}

[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface
EOF

COPY docker/bootstrap.sh /usr/bin/bootstrap
RUN chmod 777 /usr/bin/bootstrap

# Setup API
COPY ./api /opt/supervisor-api
WORKDIR /opt/supervisor-api

RUN virtualenv venv && . venv/bin/activate && pip install -r requirements.txt && deactivate
RUN cat <<EOF > /usr/bin/supervisor-api
#!/usr/bin/env bash

/opt/supervisor-api/venv/bin/python /opt/supervisor-api/api.py
EOF

RUN chmod 744 /usr/bin/supervisor-api

WORKDIR /root

EXPOSE ${API_PORT:-8000}

# Lancer supervisor a démarrage
CMD ["/usr/bin/bootstrap"]