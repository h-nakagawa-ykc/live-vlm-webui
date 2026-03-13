#!/bin/bash
# --- 
# Usage:
#     1. cd live-vlm-webui
#     2. sudo bash scripts/start_my_docker_compose.sh
# Info:
#     - `./live-vlm-webui/.env`に環境変数を記述して、`docker compose`実行時に環境変数を直接渡すようにしています
#     - 環境変数を変更する場合は、`.env`修正後、`docker compose`のサービス再起動を実行します
# ---

# docker service `live-vlm-webui`
# `depends_on:`タグの`ollama`サービスが起動してない状態でも無視して実行（VLMサーバーを独自で起動している場合を想定）
sudo docker compose --env-file .env -f docker/docker-compose.override.yml up -d --build --no-deps live-vlm-webui

# docker service `action-webhook`
sudo docker compose --env-file .env -f docker/docker-compose.override.yml up -d --build action-webhook