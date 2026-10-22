FROM python:3.12-slim
WORKDIR /srv
COPY pyproject.toml .
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic
RUN pip install --no-cache-dir .
RUN mkdir /srv/data && chown -R 65532:65532 /srv/data
USER 65532
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
