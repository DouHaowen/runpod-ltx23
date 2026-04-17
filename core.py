import json
import os
import shutil
import ssl
import subprocess
import uuid
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen


APP_DIR = Path(__file__).resolve().parent
RUNNER = APP_DIR / "runner.py"
LTX_DIR = Path(os.getenv("LTX_CODE_DIR", "/workspace/LTX-2"))
VENV_PY = Path(os.getenv("LTX_PYTHON", "/workspace/LTX-2/.venv/bin/python"))
RUNTIME_ROOT = Path(os.getenv("LTX_RUNTIME_ROOT", "/workspace/ltx23_runtime"))
JOBS_DIR = RUNTIME_ROOT / "jobs"
MEDIA_DIR = RUNTIME_ROOT / "media"
PUBLIC_BASE_URL = os.getenv("LTX_PUBLIC_BASE_URL", "").rstrip("/")
API_TOKEN = os.getenv("LTX_API_TOKEN", "").strip()

DISTILLED_CKPT = os.getenv(
    "LTX_DISTILLED_CKPT",
    "/workspace/models/LTX-2.3/ltx-2.3-22b-distilled-1.1.safetensors",
)
SPATIAL_UPSAMPLER = os.getenv(
    "LTX_SPATIAL_UPSAMPLER",
    "/workspace/models/LTX-2.3/ltx-2.3-spatial-upscaler-x2-1.1.safetensors",
)
GEMMA_ROOT = os.getenv("LTX_GEMMA_ROOT", "/workspace/models/gemma-3")

JOBS_DIR.mkdir(parents=True, exist_ok=True)
MEDIA_DIR.mkdir(parents=True, exist_ok=True)


def ensure_auth(token: str | None):
    if API_TOKEN and token != API_TOKEN:
        raise ValueError("invalid api token")


def parse_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def normalize_dim(value: int, multiple: int = 64, min_value: int = 64) -> int:
    value = max(int(value), min_value)
    remainder = value % multiple
    return value if remainder == 0 else value + (multiple - remainder)


def normalize_frames(value: int) -> int:
    value = max(int(value), 9)
    remainder = (value - 1) % 8
    if remainder == 0:
        return value
    return value + (8 - remainder)


def update_status(job_dir: Path, **updates):
    status_path = job_dir / "status.json"
    data = {}
    if status_path.exists():
        try:
            data = json.loads(status_path.read_text())
        except Exception:
            data = {}
    data.update(updates)
    status_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def load_status(job_dir: Path):
    status_path = job_dir / "status.json"
    if not status_path.exists():
        raise FileNotFoundError(f"job not found: {job_dir}")
    return json.loads(status_path.read_text())


def attach_video_url(data: dict, public_base_url: str | None = None):
    media_name = data.get("media_name")
    if not media_name:
        return data
    base = (public_base_url if public_base_url is not None else PUBLIC_BASE_URL).rstrip("/")
    data["videoUrl"] = f"{base}/media/{media_name}" if base else f"/media/{media_name}"
    return data


def status_payload(job_dir: Path, public_base_url: str | None = None):
    data = load_status(job_dir)
    return attach_video_url(data, public_base_url=public_base_url)


def create_job_dir(root: Path | None = None, job_id: str | None = None):
    root = root or JOBS_DIR
    job_id = job_id or uuid.uuid4().hex
    job_dir = root / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    return job_id, job_dir


def stage_input_image(job_dir: Path, image_bytes: bytes | None = None, image_url: str | None = None):
    if not image_bytes and not image_url:
        raise ValueError("image or image_url is required")
    image_path = job_dir / "input.png"
    if image_bytes is not None:
        image_path.write_bytes(image_bytes)
        return image_path
    ctx = ssl._create_unverified_context()
    with urlopen(image_url, context=ctx) as response:
        image_path.write_bytes(response.read())
    return image_path


def build_request(
    prompt: str,
    image_path: Path,
    width: int = 896,
    height: int = 512,
    num_frames: int = 9,
    frame_rate: int = 16,
    generate_audio=True,
):
    return {
        "prompt": prompt,
        "image_path": str(image_path),
        "width": normalize_dim(width),
        "height": normalize_dim(height),
        "num_frames": normalize_frames(num_frames),
        "frame_rate": int(frame_rate),
        "generate_audio": parse_bool(generate_audio),
    }


def ffmpeg_path():
    return subprocess.check_output(
        [str(VENV_PY), "-c", "import imageio_ffmpeg as m; print(m.get_ffmpeg_exe())"],
        text=True,
    ).strip()


def strip_audio(src: Path, dst: Path):
    subprocess.run(
        [ffmpeg_path(), "-y", "-i", str(src), "-an", "-c:v", "copy", str(dst)],
        check=True,
    )


def distilled_command(req: dict, raw_out: Path):
    return [
        str(VENV_PY),
        "-m",
        "ltx_pipelines.distilled",
        "--distilled-checkpoint-path",
        DISTILLED_CKPT,
        "--spatial-upsampler-path",
        SPATIAL_UPSAMPLER,
        "--gemma-root",
        GEMMA_ROOT,
        "--prompt",
        req["prompt"],
        "--image",
        req["image_path"],
        "0",
        "0.9",
        "--height",
        str(req.get("height", 512)),
        "--width",
        str(req.get("width", 896)),
        "--num-frames",
        str(req.get("num_frames", 9)),
        "--frame-rate",
        str(req.get("frame_rate", 16)),
        "--output-path",
        str(raw_out),
        "--quantization",
        req.get("quantization", "fp8-cast"),
        "--streaming-prefetch-count",
        str(req.get("streaming_prefetch_count", 2)),
    ]


def run_generation(req: dict, job_dir: Path):
    raw_out = job_dir / "raw.mp4"
    final_out = job_dir / "final.mp4"
    log_path = job_dir / "run.log"

    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    update_status(job_dir, status="running")

    with log_path.open("w") as logf:
        proc = subprocess.run(
            distilled_command(req, raw_out),
            cwd=str(LTX_DIR),
            stdout=logf,
            stderr=subprocess.STDOUT,
        )

    if proc.returncode != 0:
        update_status(
            job_dir,
            status="failed",
            error=f"ltx exited with code {proc.returncode}",
            log_path=str(log_path),
        )
        raise RuntimeError(f"ltx exited with code {proc.returncode}")

    if req.get("generate_audio", True):
        shutil.copy2(raw_out, final_out)
    else:
        strip_audio(raw_out, final_out)

    media_name = f"{job_dir.name}.mp4"
    media_path = MEDIA_DIR / media_name
    shutil.copy2(final_out, media_path)

    update_status(
        job_dir,
        status="completed",
        video_path=str(media_path),
        media_name=media_name,
        has_audio=bool(req.get("generate_audio", True)),
        log_path=str(log_path),
    )
    return status_payload(job_dir)


def media_url_for_name(media_name: str, public_base_url: str | None = None):
    base = (public_base_url if public_base_url is not None else PUBLIC_BASE_URL).rstrip("/")
    return f"{base}/media/{media_name}" if base else f"/media/{media_name}"


def file_name_from_url(url: str):
    path = urlparse(url).path
    return Path(path).name
