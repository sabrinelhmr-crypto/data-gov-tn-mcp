FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# pyproject.toml force l'inclusion de main.py, config.py et
# logging_config.py : le code doit etre present avant pip install, sinon
# la construction echoue sur "Forced include not found".
COPY pyproject.toml README.md ./
COPY . .

RUN pip install --no-compile . \
 && useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin mcp \
 && chown -R mcp:mcp /app

# Le service n'ecrit rien sur disque : il tourne sans privileges.
USER mcp

EXPOSE 8000

CMD ["python", "main.py"]
