FROM python:3.12-slim
WORKDIR /srv
COPY pyproject.toml .
COPY healops_worker ./healops_worker
RUN pip install --no-cache-dir .
CMD ["healops-worker"]
