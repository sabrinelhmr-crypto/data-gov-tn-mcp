FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml .
COPY README.md .
RUN pip install --no-cache-dir .
COPY . .
EXPOSE 8000
CMD ["python", "main.py"]
