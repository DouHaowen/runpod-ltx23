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
- Returns:
  - `ok`
  - `jobId`
  - `status`
  - `videoPath`
  - `videoUrl` when `LTX_PUBLIC_BASE_URL` is configured
  - `hasAudio`

## Remaining production work

1. Decide final media publishing strategy for Serverless output
   - public object storage URL
   - or shared mounted volume with a separate media host
2. Build and publish the worker image
3. Create a RunPod Serverless endpoint, preferably Flex workers first
4. Point `waoowaoo` from the temporary Pod tunnel to the new endpoint
