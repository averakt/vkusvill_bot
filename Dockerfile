FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY vendor/vv_mcp /opt/vv_mcp
RUN pip install --no-cache-dir /opt/vv_mcp

COPY . .

CMD ["python", "-u", "telegram_bot.py"]