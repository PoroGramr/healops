FROM node:22-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g @openai/codex@0.162.1 \
    && mkdir -p /home/node/.codex \
    && chown -R 1000:1000 /home/node
USER 1000:1000
ENV HOME=/home/node CODEX_HOME=/home/node/.codex
WORKDIR /home/node
ENTRYPOINT ["codex", "exec"]
