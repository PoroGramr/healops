FROM python:3.12-slim
WORKDIR /srv
COPY pyproject.toml .
COPY healops_executor ./healops_executor
RUN pip install --no-cache-dir .
CMD ["healops-executor"]
