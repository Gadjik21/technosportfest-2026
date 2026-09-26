FROM docker:27-cli AS docker-cli

FROM python:3.12-slim

WORKDIR /app
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

USER 1000:1000
CMD ["python", "-m", "app.judge_worker"]
