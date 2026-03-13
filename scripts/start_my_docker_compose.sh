#!/bin/bash
# --- 
# Usage:
#     1. cd live-vlm-webui
#     2. sudo bash scripts/start_my_docker_compose.sh
# ---

# docker service `live-vlm-webui`
# `depends_on:`タグの`ollama`サービスが起動してない状態でも無視して実行（VLMサーバーを独自で起動している場合を想定）
sudo docker compose --env-file .env -f docker/docker-compose.override.yml up -d --build --no-deps live-vlm-webui

# docker service `action-webhook`
sudo docker compose --env-file .env -f docker/docker-compose.override.yml up -d --build action-webhook