FROM python:3.13-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install uv

COPY requirements.txt .
RUN uv pip install --system -r requirements.txt

COPY . .

RUN useradd -m -u 1001 appuser \
    && mkdir -p /app/instance /app/logs /app/app/static/uploads \
    && chown -R appuser:appuser /app/instance /app/logs /app/app/static/uploads

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER appuser

EXPOSE 5000
ENTRYPOINT ["/entrypoint.sh"]
