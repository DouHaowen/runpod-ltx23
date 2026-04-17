# runpod-ltx23

RunPod deployment scaffold for `LTX-2.3`, extracted from the working Pod setup already integrated with `waoowaoo`.

## Goals

- Pod mode: expose a small HTTP API for image-to-video.
- Support both:
  - native audio on
  - native audio off
- Reuse the same core runner for a future RunPod Serverless worker.

## Current status

- Pod mode structure is implemented in this repo.
- Shared generation core is implemented in `core.py`.
- Serverless layout now reuses the same generation core as Pod mode.

## API contract

### `GET /health`

Returns:

```json
{ "ok": true }
```

### `POST /generate`

Multipart form fields:

- `prompt`
- `image` or `image_url`
- `width`
- `height`
- `num_frames`
- `frame_rate`
- `generate_audio`
- `token`

Returns:

```json
{
  "jobId": "abc123",
  "status": "queued"
}
```

### `GET /jobs/{job_id}`

Returns status and final media URL when completed.

## Environment

Copy `.env.example` to `.env` and fill the values you need.

Important runtime assumptions:

- The official `LTX-2` repo is available on the machine.
- The `LTX-2` virtualenv already exists.
- Model files are already downloaded.

## Pod mode

Run:

```bash
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8888
```

## Docker

This repo includes a baseline `Dockerfile` for Pod usage. It is intentionally conservative so we can harden it before the Serverless cutover.

## Serverless

See [serverless/README.md](serverless/README.md).

## Repository structure

- `core.py`: shared request normalization and LTX execution logic
- `app.py`: Pod-mode FastAPI wrapper
- `runner.py`: subprocess entrypoint for Pod-mode async jobs
- `serverless/handler.py`: RunPod Serverless handler using the same core logic
