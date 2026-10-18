# InvoiceLens demo image. Hugging Face Spaces (Docker SDK) compatible: listens on 7860, runs as uid 1000.
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH \
    DEMO_MODE=true PYTHONUNBUFFERED=1 \
    REVIEW_DB_PATH=/tmp/invoicelens/review.db TMPDIR=/tmp
WORKDIR /home/user/app

COPY --chown=user pyproject.toml README.md ./
COPY --chown=user src ./src
COPY --chown=user config ./config
COPY --chown=user data ./data
RUN pip install --no-cache-dir -e .

# ANTHROPIC_API_KEY must be provided as a runtime secret (Space secret / docker -e). Never bake it in.
EXPOSE 7860
# --proxy-headers so per-IP limits see the real client behind the Spaces proxy.
CMD ["uvicorn", "invoicelens.web.app:app", "--host", "0.0.0.0", "--port", "7860", "--proxy-headers", "--forwarded-allow-ips", "*"]
