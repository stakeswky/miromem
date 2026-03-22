FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi>=0.104.0 \
    uvicorn>=0.24.0 \
    httpx>=0.25.0 \
    pydantic>=2.5.0 \
    motor>=3.3.0 \
    openai>=1.0.0 \
    python-dotenv>=1.0.0

COPY . /app/miromem
ENV PYTHONPATH=/app

EXPOSE 8000
CMD ["uvicorn", "miromem.gateway.app:app", "--host", "0.0.0.0", "--port", "8000"]
