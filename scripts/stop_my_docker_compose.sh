#!/bin/bash
# --- 
# Usage:
#     1. cd live-vlm-webui
#     2. sudo bash scripts/stop_my_docker_compose.sh
# ---

# docker service `live-vlm-webui`
sudo docker compose -f docker/docker-compose.override.yml stop live-vlm-webui
sudo docker compose -f docker/docker-compose.override.yml down live-vlm-webui

# docker service `action-webhook`
sudo docker compose -f docker/docker-compose.override.yml stop action-webhook
sudo docker compose -f docker/docker-compose.override.yml down action-webhook
