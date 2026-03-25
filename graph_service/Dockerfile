FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi>=0.104.0 \
    uvicorn>=0.24.0 \
    httpx>=0.25.0 \
    pydantic>=2.5.0 \
    pydantic-settings>=2.0.0 \
    openai>=1.0.0 \
    graphiti-core[falkordb]>=0.28.2

COPY __init__.py /app/miromem/__init__.py
COPY graph_service /app/miromem/graph_service

ENV PYTHONPATH=/app

EXPOSE 8001

CMD ["uvicorn", "miromem.graph_service.app:app", "--host", "0.0.0.0", "--port", "8001"]
