import asyncio

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import StreamingResponse
import xmlrpc.client
import os
from pathlib import Path

app = FastAPI()

# Expected job states (optional, for validation)
EXPECTED_STATES = {
    "worker": "RUNNING",
    "cron": "RUNNING",
}

# Supervisor API config
_supervisor_user = os.environ.get('ADMIN_USERNAME', '')
_supervisor_pass = os.environ.get('ADMIN_PASSWORD', '')
SUPERVISOR_URL = f"http://{_supervisor_user}:{_supervisor_pass}@localhost:9001/RPC2"
SUPERVISOR = xmlrpc.client.ServerProxy(SUPERVISOR_URL)

# Log directory (must match supervisord.conf)
LOG_DIR = "/var/log"

@app.get("/health")
def health_check_all():
    """Check the status of all Supervisor jobs."""
    try:
        processes = SUPERVISOR.supervisor.getAllProcessInfo()
        status = {process["name"]: process["statename"] for process in processes}
        all_ok = all(
            status.get(job, "UNKNOWN") == EXPECTED_STATES.get(job, "RUNNING")
            for job in EXPECTED_STATES
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
        expected_state = EXPECTED_STATES.get(job_name, "RUNNING")
        if job_status["statename"] == expected_state:
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
                    "expected": expected_state,
                },
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail={"status": "error", "message": str(e)})

def get_job_log_paths():
    """Return a dict of job names to their log file paths."""
    try:
        processes = SUPERVISOR.supervisor.getAllProcessInfo()
        log_paths = {}
        for process in processes:
            job_name = process["name"]
            # Assume stdout and stderr logs follow the pattern: /var/log/{job_name}.{out,err}.log
            stdout_log = f"{LOG_DIR}/{job_name}.out.log"
            stderr_log = f"{LOG_DIR}/{job_name}.err.log"
            log_paths[job_name] = {
                "stdout": stdout_log if Path(stdout_log).exists() else None,
                "stderr": stderr_log if Path(stderr_log).exists() else None,
            }
        return log_paths
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch job log paths: {str(e)}")

@app.get("/logs")
def list_logs():
    """List all available job logs."""
    log_paths = get_job_log_paths()
    return {"logs": log_paths}

@app.get("/logs/{job_name}")
def tail_log(
    job_name: str,
    lines: int = 100,
    stream: str = None,  # "stdout" or "stderr"
):
    """
    Tail the last `lines` of a job's log file.
    If `stream` is not specified, returns both stdout and stderr (if available).
    """
    log_paths = get_job_log_paths()
    if job_name not in log_paths:
        raise HTTPException(status_code=404, detail=f"Job '{job_name}' not found.")

    logs = log_paths[job_name]
    if stream:
        if stream not in logs or not logs[stream]:
            raise HTTPException(
                status_code=404,
                detail=f"Log stream '{stream}' not found for job '{job_name}'."
            )
        log_file = logs[stream]
        return tail_file(log_file, lines)
    else:
        # Return both stdout and stderr if available
        result = {}
        if logs["stdout"]:
            result["stdout"] = tail_file(logs["stdout"], lines)
        if logs["stderr"]:
            result["stderr"] = tail_file(logs["stderr"], lines)
        return result

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
            # Seek to the end of the file
            f.seek(0, os.SEEK_END)
            while True:
                line = f.readline()
                if line:
                    yield f"data: {line}\n\n"
                else:
                    # Wait for new lines
                    await asyncio.sleep(0.1)

    return StreamingResponse(generate(), media_type="text/event-stream")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('API_PORT', 80)))