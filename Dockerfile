FROM debian:trixie-slim

RUN apt update -y && apt upgrade -y --fix-missing && apt install -y supervisor

# Initialize supervisor configuration
RUN cat <<EOF > /etc/supervisor/conf.d/supervisord.conf
[supervisord]
user=root
nodaemon=true
#logfile=/dev/stdout
#pidfile=/tmp/supervisord.pid

[inet_http_server]
port = *:9001
username = {{ADMIN_USERNAME}}
password = {{ADMIN_PASSWORD}}

[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface
EOF

COPY docker/bootstrap.sh /usr/bin/bootstrap
RUN chmod 777 /usr/bin/bootstrap

# Lancer supervisor a démarrage
CMD ["/usr/bin/bootstrap"]