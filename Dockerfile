# Run with a Playwright image that has the right glibc/libstdc++
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

WORKDIR /app

# Leverage layer caching for deps
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m playwright install --with-deps chromium

COPY . .

ENV PYTHONUNBUFFERED=1

# Default to continuous monitor; override with --once as needed
CMD ["python", "run.py"]

