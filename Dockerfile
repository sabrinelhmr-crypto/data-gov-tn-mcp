FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml .
COPY README.md .
RUN pip install --no-cache-dir .
COPY . .
EXPOSE 8000
CMD ["python", "main.py"]
