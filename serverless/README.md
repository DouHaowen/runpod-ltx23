# Serverless plan

This directory contains the RunPod Serverless entrypoint for `LTX-2.3`.

## Current behavior

- Accepts a RunPod job payload under `job["input"]`
- Reuses the same shared generation logic as Pod mode via `core.py`
- Supports:
  - `prompt`
  - `image_base64` or `image_url`
  - `width`
  - `height`
  - `num_frames`
  - `frame_rate`
  - `generate_audio`
  - optional `result_upload_url`
- Returns:
  - `ok`
  - `jobId`
  - `status`
  - `videoPath`
  - `videoUrl` when `LTX_PUBLIC_BASE_URL` is configured
  - `hasAudio`
  - `uploadStatus` when a final upload URL is provided

## Remaining production work

1. Decide whether `waoowaoo` will pass a presigned upload URL for final mp4 delivery
2. Build and publish the worker image
3. Create a RunPod Serverless endpoint, preferably Flex workers first
4. Point `waoowaoo` from the temporary Pod tunnel to the new endpoint
