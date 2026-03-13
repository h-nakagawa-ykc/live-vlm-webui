#!/bin/bash
# --- 
# Usage:
#     1. cd live-vlm-webui
#     2. sudo bash scripts/stop_my_docker_compose.sh
# Info:
#     - `./live-vlm-webui/.env`に環境変数を記述して、`docker compose`実行時に環境変数を直接渡すようにしています
#     - 環境変数を変更する場合は、`.env`修正後、`docker compose`のサービス再起動を実行します
# ---

# docker service `live-vlm-webui`
sudo docker compose -f docker/docker-compose.override.yml stop live-vlm-webui
sudo docker compose -f docker/docker-compose.override.yml down live-vlm-webui

# docker service `action-webhook`
sudo docker compose -f docker/docker-compose.override.yml stop action-webhook
sudo docker compose -f docker/docker-compose.override.yml down action-webhook
