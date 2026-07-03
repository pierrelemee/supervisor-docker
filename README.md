# supervisor-docker

A Docker image to run supervisor with some handful of tools and a REST API to manage jobs.

It embeds `supervisor` with an HTTP API that offers services to monitor the activity of running commands.

## Configuration

### Jobs

You can configure the commands to run in the `SUPERVISOR_CONFIG` environment variable.

It can either be the path of a file mounted on the container or the configuration itself.

The format of the configuration should follow [the official documentation of the `program` section](https://supervisord.org/configuration.html#program-x-section-settings).

### API access

You must define the `SUPERVISOR_API_USERNAME` and `SUPERVISOR_API_PASSWORD` to restrict access to the API.

You can also define the `SUPERVISOR_API_PORT` to change the port the API will be listening to (dafault is `8000`).

## Interacting with the API

The API uses auth basic authentication from the specified  `SUPERVISOR_API_USERNAME` and `SUPERVISOR_API_PASSWORD` values.

### Job status

You can check if a job is running by calliong the `GET /health/{job}` endpoint :

```sh
curl -u ${SUPERVISOR_API_USERNAME}:${SUPERVISOR_API_PASSWORD} http://localhost:8000/health/myjob
```

If the job is running, the enpoint will return a `200 OK` response with this JSON content :

```json
{
  "status": "ok",
  "job": "myjob",
  "state": "RUNNING"
}
```

Otherwise, a `500 SERVER ERROR` will be returned, to align with monitoring tools APIs, with response as such :

```json
{
  "status": "error",
  "job": "myjob",
  "state": "ABORTED"
}
```

If no such job exists in the `SUPERVISOR_CONFIG`, a `404 NOT FOUND` will be returned.

### Job logs

You can get the logs of a given job by invoking the `GET /logs/{job}/{stream}` endpoint : 

```sh
curl -u ${SUPERVISOR_API_USERNAME}:${SUPERVISOR_API_PASSWORD} http://localhost:8000/logs/myjob/out?lines=300
```

The `stream` path must be either `out` or `err` for respectively stdout and stderr job streams.

The `lines` query parameter allow you to restrict to the last `lines` lines of the job logs (default to `100`).

The response will be in plain text.

If no such job exists in the `SUPERVISOR_CONFIG`, a `404 NOT FOUND` will be returned.

You can also access the live stream with the `GET /logs/{job}/follow/{stream}` endpoint :

```sh
curl -u ${SUPERVISOR_API_USERNAME}:${SUPERVISOR_API_PASSWORD} http://localhost:8000/logs/myjob/follow/out
```

This endpoint allows to prefix each log line by its timestamp in milliseconds by setting the `timed` query parameter with a truey value (`true`, `t`, `yes` or `1`) or a falsy one (default to `false`).

## The Docker image

The image is built using [buildx](https://docs.docker.com/buildx/working-with-buildx/) and is available on [Docker Hub](https://hub.docker.com/r/pierrelemee/supervisor-docker) :

```bash
docker buildx build --platform linux/amd64,linux/arm64 . -t pierrelemee/supervisor-docker:<tag>
```

You can extend the image with [Docker _multi-stage_ build](https://docs.docker.com/build/building/multi-stage/) by doing so :

```Dockerfile
FROM pierrelemee/supervisor-docker:latest AS supervisor

FROM base-image:version AS base

COPY --from=supervisor /opt/supervisor-api /opt/supervisor-api

# ... declare your steps here

# This step is required to override any `CMD` directive from `base-image 
CMD ["/opt/supervisor-api/supervisor-api"]
```
