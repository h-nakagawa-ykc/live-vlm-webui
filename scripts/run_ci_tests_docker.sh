#!/bin/bash
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -euo pipefail

PY_IMAGE="${PY_IMAGE:-python:3.11-slim-bullseye}"

if [ "$#" -gt 0 ]; then
  TEST_TARGETS="$*"
else
  TEST_TARGETS="tests/unit/test_event_dispatcher.py tests/unit/test_vlm_service_webhook_resilience.py tests/unit/test_action_webhook_rules.py"
fi

echo "Running CI-like tests in Docker"
echo "Python image: ${PY_IMAGE}"
echo "Test targets: ${TEST_TARGETS}"

docker run --rm -t \
  -v "$PWD":/work \
  -w /work \
  "${PY_IMAGE}" \
  bash -lc "
    apt-get update &&
    apt-get install -y --no-install-recommends \
      libglib2.0-0 libsm6 libxext6 libxrender1 libxcb1 libgl1 &&
    rm -rf /var/lib/apt/lists/* &&
    python -m pip install -U pip &&
    pip install -e '.[dev]' &&
    python -m pytest ${TEST_TARGETS} -v
  "

echo "Docker CI-like test run completed successfully"
