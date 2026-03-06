# Webhook Event Payload Schema v1.1

## Overview
This document defines the webhook payload schema for VLM inference events.

## Event Type
- `event_type`: `vlm_inference_result`

## Common Fields (Required)
- `event_id` (string): unique event identifier
- `event_type` (string): fixed value `vlm_inference_result`
- `timestamp_unix` (number): Unix timestamp (seconds)
- `mode` (string): `single` or `multi`
- `text` (string): VLM output text
- `model` (string): model name
- `api_base` (string): API base URL

## Common Fields (Optional)
- `metrics` (object):
  - `last_latency_ms` (number)
  - `avg_latency_ms` (number)
  - `total_inferences` (number)
  - `is_processing` (boolean)
- `risk_score` (number): normalized risk score in `[0.0, 1.0]`
- `labels` (array[string]): optional labels extracted from structured VLM output
- `camera_id` (string): input source camera identifier
- `stream_id` (string): stream/session identifier
- `inference_prompt_id` (string): prompt identifier used for this inference
  - Default format in current implementation: `sha256:<16-hex>`
  - Can be overridden by env var `LIVE_VLM_INFERENCE_PROMPT_ID`

## Multi-frame Fields (Optional)
- `selected_frame_count` (integer): number of selected representative frames
- `buffered_frame_count` (integer): number of buffered frames used in cycle
- `used_fallback` (boolean): true if multi-image failed and per-frame fallback was used

## Extraction Rules for Optional Fields
- `risk_score` and `labels` are extracted only when `text` is valid JSON object and fields are valid.
- Invalid or missing values are ignored (field omitted).
- `camera_id` / `stream_id` / `inference_prompt_id` are optional and may be absent.

## Example: Single
```json
{
  "event_id": "2f3c1d1a-0000-1111-2222-333344445555",
  "event_type": "vlm_inference_result",
  "timestamp_unix": 1760000000.123,
  "mode": "single",
  "text": "{\"answer\":\"yes\",\"risk_score\":0.82,\"labels\":[\"person\",\"smoke\"]}",
  "model": "llama-3.2-11b-vision-instruct",
  "api_base": "http://localhost:11434/v1",
  "risk_score": 0.82,
  "labels": ["person", "smoke"],
  "camera_id": "cam-entrance-01",
  "stream_id": "rtsp-session-a",
  "inference_prompt_id": "sha256:8e0e5f3f4f8d6a8b",
  "metrics": {
    "last_latency_ms": 420.5,
    "avg_latency_ms": 510.2,
    "total_inferences": 12,
    "is_processing": false
  }
}
```

## Example: Multi
```json
{
  "event_id": "9a8b7c6d-aaaa-bbbb-cccc-ddddeeeeffff",
  "event_type": "vlm_inference_result",
  "timestamp_unix": 1760000010.456,
  "mode": "multi",
  "text": "[Frame 1] ...",
  "model": "llama-3.2-11b-vision-instruct",
  "api_base": "http://localhost:11434/v1",
  "camera_id": "cam-yard-02",
  "stream_id": "yard-session",
  "inference_prompt_id": "sha256:8e0e5f3f4f8d6a8b",
  "selected_frame_count": 4,
  "buffered_frame_count": 8,
  "used_fallback": true,
  "metrics": {
    "last_latency_ms": 980.1,
    "avg_latency_ms": 760.4,
    "total_inferences": 13,
    "is_processing": false
  }
}
```

## Compatibility Policy
- New fields may be added in future versions.
- Receivers must ignore unknown fields.
- Existing field meanings will not be changed in v1.x.
- Breaking changes require a new major schema version.
