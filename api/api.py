import asyncio
import argparse
import configparser
import sys

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import StreamingResponse
import xmlrpc.client
import os
from pathlib import Path


def load_supervisor_config(config_path: str) -> configparser.ConfigParser:
    path = Path(config_path)
    if not path.exists():
        print(f"Error: config file '{config_path}' does not exist.", file=sys.stderr)
        sys.exit(1)
    config = configparser.ConfigParser()
    config.read(path)
    return config


def parse_programs(config: configparser.ConfigParser) -> dict:
    """Extract program definitions from [program:*] sections."""
    programs = {}
    for section in config.sections():
        if section.startswith('program:'):
            name = section[len('program:'):]
            programs[name] = dict(config[section])
    return programs


# Parse --config CLI arg (parse_known_args to tolerate uvicorn's own args)
_parser = argparse.ArgumentParser()
_parser.add_argument('--config', required=True, help='Path to supervisord config file')
_args, _ = _parser.parse_known_args()

_supervisor_config = load_supervisor_config(_args.config)
KNOWN_PROGRAMS = parse_programs(_supervisor_config)

app = FastAPI()

# Supervisor API config
_supervisor_user = os.environ.get('ADMIN_USERNAME', '')
_supervisor_pass = os.environ.get('ADMIN_PASSWORD', '')
SUPERVISOR_URL = f"http://{_supervisor_user}:{_supervisor_pass}@localhost:9001/RPC2"
SUPERVISOR = xmlrpc.client.ServerProxy(SUPERVISOR_URL)


@app.get("/health")
def health_check_all():
    """Check the status of all known Supervisor jobs."""
    try:
        processes = SUPERVISOR.supervisor.getAllProcessInfo()
        status = {process["name"]: process["statename"] for process in processes}
        all_ok = all(
            status.get(job, "UNKNOWN") == "RUNNING"
            for job in KNOWN_PROGRAMS
        )
        if all_ok:
            return {"status": "ok", "jobs": status}
        else:
            raise HTTPException(status_code=500, detail={"status": "error", "jobs": status})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"status": "error", "message": str(e)})


@app.get("/health/{job_name}")
def health_check_job(job_name: str):
    """Check the status of a specific Supervisor job by name."""
    if job_name not in KNOWN_PROGRAMS:
        raise HTTPException(status_code=404, detail=f"Job '{job_name}' not found in config.")
    try:
        processes = SUPERVISOR.supervisor.getAllProcessInfo()
        job_status = next(
            (p for p in processes if p["name"] == job_name),
            None
        )
        if not job_status:
            raise HTTPException(
                status_code=404,
                detail=f"Job '{job_name}' not found in Supervisor."
            )
        if job_status["statename"] == "RUNNING":
            return {
                "status": "ok",
                "job": job_name,
                "state": job_status["statename"],
            }
        else:
            raise HTTPException(
                status_code=500,
                detail={
                    "status": "error",
                    "job": job_name,
                    "state": job_status["statename"],
                    "expected": "RUNNING",
                },
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail={"status": "error", "message": str(e)})


def get_job_log_paths() -> dict:
    """Return a dict of job names to their log file paths, sourced from config."""
    log_paths = {}
    for name, settings in KNOWN_PROGRAMS.items():
        stdout_log = settings.get('stdout_logfile')
        stderr_log = settings.get('stderr_logfile')
        log_paths[name] = {
            "stdout": stdout_log if stdout_log and Path(stdout_log).exists() else None,
            "stderr": stderr_log if stderr_log and Path(stderr_log).exists() else None,
        }
    return log_paths

@app.get("/logs/{job_name}/{stream}")
def tail_log(
    job_name: str,
    stream: str,  # "out" or "err"
    lines: int = 100,
):
    """
    Tail the last `lines` of a job's log file.
    `stream` must be either 'out' (stdout) or 'err' (stderr).
    """
    log_paths = get_job_log_paths()
    if job_name not in log_paths:
        raise HTTPException(status_code=404, detail=f"Job '{job_name}' not found.")

    stream_key = {"out": "stdout", "err": "stderr"}.get(stream)
    if not stream_key:
        raise HTTPException(status_code=400, detail=f"Invalid stream '{stream}': must be 'out' or 'err'.")

    logs = log_paths[job_name]
    if not logs[stream_key]:
        raise HTTPException(
            status_code=404,
            detail=f"Log stream '{stream}' not found for job '{job_name}'."
        )
    return tail_file(logs[stream_key], lines)


def tail_file(file_path: str, lines: int = 100):
    """Return the last `lines` of a file."""
    try:
        with open(file_path, "r") as f:
            return "".join(f.readlines()[-lines:])
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Log file '{file_path}' not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read log file: {str(e)}")


@app.get("/logs/{job_name}/stream")
async def stream_log(job_name: str, stream: str = "stdout"):
    """
    Stream a job's log file in real-time using Server-Sent Events (SSE).
    Usage: `curl http://localhost:5000/logs/worker/stream?stream=stdout`
    """
    log_paths = get_job_log_paths()
    if job_name not in log_paths:
        raise HTTPException(status_code=404, detail=f"Job '{job_name}' not found.")

    logs = log_paths[job_name]
    if stream not in logs or not logs[stream]:
        raise HTTPException(
            status_code=404,
            detail=f"Log stream '{stream}' not found for job '{job_name}'."
        )

    log_file = logs[stream]

    async def generate():
        with open(log_file, "r") as f:
            f.seek(0, os.SEEK_END)
            while True:
                line = f.readline()
                if line:
                    yield f"data: {line}\n\n"
                else:
                    await asyncio.sleep(0.1)

    return StreamingResponse(generate(), media_type="text/event-stream")


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('API_PORT', 80)))
