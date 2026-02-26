# Webhook Event Payload Schema v1

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

## Multi-frame Fields (Optional)
- `selected_frame_count` (integer): number of selected representative frames
- `buffered_frame_count` (integer): number of buffered frames used in cycle
- `used_fallback` (boolean): true if multi-image failed and per-frame fallback was used

## Example: Single
```json
{
  "event_id": "2f3c1d1a-0000-1111-2222-333344445555",
  "event_type": "vlm_inference_result",
  "timestamp_unix": 1760000000.123,
  "mode": "single",
  "text": "A person is standing near a desk.",
  "model": "llama-3.2-11b-vision-instruct",
  "api_base": "http://localhost:11434/v1",
  "metrics": {
    "last_latency_ms": 420.5,
    "avg_latency_ms": 510.2,
    "total_inferences": 12,
    "is_processing": false
  }
}

## Example: Multi

{
  "event_id": "9a8b7c6d-aaaa-bbbb-cccc-ddddeeeeffff",
  "event_type": "vlm_inference_result",
  "timestamp_unix": 1760000010.456,
  "mode": "multi",
  "text": "[Frame 1] ...",
  "model": "llama-3.2-11b-vision-instruct",
  "api_base": "http://localhost:11434/v1",
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

## Compatibility Policy

- New fields may be added in future versions.
- Receivers must ignore unknown fields.
- Existing field meanings will not be changed in v1.
- Breaking changes require a new schema version.


