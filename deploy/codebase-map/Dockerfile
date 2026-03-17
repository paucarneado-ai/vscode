FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Clone repo at build time
ARG REPO_URL=https://github.com/paucarneado-ai/vscode
ARG REPO_BRANCH=main
RUN git clone --depth 1 --branch ${REPO_BRANCH} ${REPO_URL} /app/repo

# Setup generator workspace
RUN mkdir -p /app/static /app/www && \
    cp /app/repo/scripts/generate_map.py /app/ && \
    cp /app/repo/static/codebase-map-template.html /app/static/ && \
    (cp /app/repo/scripts/d3.v7.min.js /app/ 2>/dev/null || true) && \
    (cp /app/repo/scripts/dagre.min.js /app/ 2>/dev/null || true) && \
    cp /app/repo/deploy/codebase-map/serve.py /app/

# Point generator at cloned repo
ENV PROJECT_ROOT=/app/repo
ENV REPO_BRANCH=${REPO_BRANCH}

# Generate initial map
RUN python /app/generate_map.py && \
    cp /app/static/codebase-map.html /app/www/index.html

EXPOSE 80

CMD ["python", "/app/serve.py"]
