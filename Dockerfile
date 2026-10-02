FROM python:3.12-slim

WORKDIR /app
RUN useradd --create-home --uid 10001 llmgateway
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir .
USER llmgateway
EXPOSE 8080
CMD ["uvicorn", "llm_gateway.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080", "--no-server-header"]
