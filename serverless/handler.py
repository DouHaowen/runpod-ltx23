import base64
import tempfile
from pathlib import Path

import runpod

from core import build_request, create_job_dir, run_generation, stage_input_image


SERVERLESS_ROOT = Path("/tmp/ltx23_serverless")
SERVERLESS_ROOT.mkdir(parents=True, exist_ok=True)


def _image_bytes_from_input(job_input: dict):
    image_b64 = job_input.get("image_base64") or job_input.get("image")
    if not image_b64:
        return None
    if isinstance(image_b64, str) and image_b64.startswith("data:"):
        image_b64 = image_b64.split(",", 1)[1]
    return base64.b64decode(image_b64)


def handler(job):
    job_input = (job or {}).get("input", {})
    prompt = (job_input.get("prompt") or "").strip()
    if not prompt:
        return {"ok": False, "error": "prompt is required"}

    try:
        with tempfile.TemporaryDirectory(dir=str(SERVERLESS_ROOT)) as temp_dir:
            _, job_dir = create_job_dir(Path(temp_dir), job_id=(job or {}).get("id"))
            image_path = stage_input_image(
                job_dir,
                image_bytes=_image_bytes_from_input(job_input),
                image_url=job_input.get("image_url"),
            )
            req = build_request(
                prompt=prompt,
                image_path=image_path,
                width=int(job_input.get("width", 896)),
                height=int(job_input.get("height", 512)),
                num_frames=int(job_input.get("num_frames", 9)),
                frame_rate=int(job_input.get("frame_rate", 16)),
                generate_audio=job_input.get("generate_audio", True),
            )
            if "quantization" in job_input:
                req["quantization"] = job_input["quantization"]
            if "streaming_prefetch_count" in job_input:
                req["streaming_prefetch_count"] = int(job_input["streaming_prefetch_count"])

            result = run_generation(req, job_dir)
            return {
                "ok": True,
                "jobId": job_dir.name,
                "status": result.get("status"),
                "videoPath": result.get("video_path"),
                "videoUrl": result.get("videoUrl"),
                "hasAudio": result.get("has_audio"),
                "mediaName": result.get("media_name"),
                "logPath": result.get("log_path"),
            }
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


runpod.serverless.start({"handler": handler})
