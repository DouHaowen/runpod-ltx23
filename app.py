import json
import subprocess
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from core import (
    APP_DIR,
    JOBS_DIR,
    MEDIA_DIR,
    RUNNER,
    VENV_PY,
    build_request,
    create_job_dir,
    ensure_auth,
    stage_input_image,
    status_payload,
)

app = FastAPI(title="LTX 2.3 API", version="0.1.0")
app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/generate")
async def generate(
    prompt: str = Form(...),
    image: UploadFile | None = File(None),
    image_url: str | None = Form(None),
    width: int = Form(896),
    height: int = Form(512),
    num_frames: int = Form(9),
    frame_rate: int = Form(16),
    generate_audio: str = Form("true"),
    token: str | None = Form(None),
):
    try:
        ensure_auth(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if not image and not image_url:
        raise HTTPException(status_code=400, detail="image or image_url is required")

    job_id, job_dir = create_job_dir(JOBS_DIR)
    image_path = stage_input_image(
        job_dir,
        image_bytes=await image.read() if image is not None else None,
        image_url=image_url,
    )
    req = build_request(
        prompt=prompt,
        image_path=image_path,
        width=width,
        height=height,
        num_frames=num_frames,
        frame_rate=frame_rate,
        generate_audio=generate_audio,
    )
    (job_dir / "request.json").write_text(json.dumps(req, ensure_ascii=False, indent=2))
    (job_dir / "status.json").write_text(json.dumps({"status": "queued"}, indent=2))

    subprocess.Popen(
        [str(VENV_PY), str(RUNNER), str(job_dir / "request.json")],
        cwd=str(APP_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    return {"jobId": job_id, "status": "queued"}


@app.get("/jobs/{job_id}")
def job_status(job_id: str, token: str | None = None):
    try:
        ensure_auth(token)
        return status_payload(JOBS_DIR / job_id)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="job not found") from exc


@app.get("/jobs/{job_id}/log")
def job_log(job_id: str, token: str | None = None):
    try:
        ensure_auth(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    job_dir = JOBS_DIR / job_id
    try:
        data = status_payload(job_dir)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="job not found") from exc
    log_path = data.get("log_path")
    if not log_path or not Path(log_path).exists():
        raise HTTPException(status_code=404, detail="log not found")
    return FileResponse(log_path, media_type="text/plain")
