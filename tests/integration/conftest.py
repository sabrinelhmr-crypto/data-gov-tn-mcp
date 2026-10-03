"""
Fixtures des tests d'integration.

Elles montent le vrai serveur : application ASGI FastMCP, pile de middlewares
(protection Host/Origin, limitation de debit) et un vrai client MCP qui parle
JSON-RPC 2.0 sur le transport Streamable HTTP. Aucun port n'est ouvert : le
client recoit un transport httpx branches sur l'application en memoire.
"""

import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
import pytest
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

import main

HOST = "mcp.data.gov.tn"
SERVER_URL = f"http://{HOST}"


class LifespanRunner:
    """
    Joue le protocole lifespan ASGI autour d'un bloc.

    Le gestionnaire de sessions Streamable HTTP de FastMCP demarre au
    ``lifespan.startup`` : sans lui, tout appel ``/mcp`` echoue. Ce runner
    remplace la dependance ``asgi-lifespan``, pour rester sans dependance
    de test supplémentaire.
    """

    def __init__(self, app: Any, timeout: float = 10.0) -> None:
        self.app = app
        self.timeout = timeout

    async def __aenter__(self) -> "LifespanRunner":
        self._inbox: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._startup = asyncio.Event()
        self._shutdown = asyncio.Event()

        async def send(message: dict[str, Any]) -> None:
            if message["type"] == "lifespan.startup.complete":
                self._startup.set()
            elif message["type"] == "lifespan.shutdown.complete":
                self._shutdown.set()
            elif message["type"] == "lifespan.startup.failed":
                self._startup.set()
                raise RuntimeError(message.get("message", "demarrage ASGI refuse"))

        self._task = asyncio.create_task(
            self.app(
                {"type": "lifespan", "asgi": {"version": "3.0"}, "state": {}}, self._inbox.get, send
            )
        )
        await self._inbox.put({"type": "lifespan.startup"})
        await asyncio.wait_for(self._startup.wait(), timeout=self.timeout)
        return self

    async def __aexit__(self, *exc: object) -> bool:
        await self._inbox.put({"type": "lifespan.shutdown"})
        await asyncio.wait_for(self._shutdown.wait(), timeout=self.timeout)
        self._task.cancel()
        return False


def client_factory(
    app: Any, base_url: str = SERVER_URL, **kwargs: Any
) -> Callable[..., httpx.AsyncClient]:
    """Fabrique le client httpx du protocole MCP, branche sur l'app en memoire."""

    def factory(**_: Any) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url=base_url,
            **kwargs,
        )

    return factory


def build_app() -> Any:
    """Reconstruit l'application avec la configuration de test."""
    return main.create_app()


@pytest.fixture
def asgi_app() -> Any:
    """Application ASGI du serveur, avec un compteur de debit neuf."""
    main.rate_limiter.reset()
    return build_app()


@pytest.fixture
async def mcp_client(asgi_app: Any) -> AsyncIterator[Client]:
    """Client MCP reel, en Streamable HTTP, sur l'application du serveur."""
    transport = StreamableHttpTransport(
        f"{SERVER_URL}/mcp",
        httpx_client_factory=client_factory(asgi_app),
    )
    async with LifespanRunner(asgi_app):
        async with Client(transport) as client:
            yield client


@pytest.fixture
async def http_client(asgi_app: Any) -> AsyncIterator[httpx.AsyncClient]:
    """Client HTTP brut, pour les endpoints hors protocole (/health, 429...)."""
    async with LifespanRunner(asgi_app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=asgi_app),
            base_url=SERVER_URL,
        ) as client:
            yield client


@pytest.fixture
def text_of(result: Any) -> str:
    """Extrait le texte du premier contenu textuel d'un resultat d'outil MCP."""

    def extract(result: Any = result) -> str:
        first = result.content[0]
        return getattr(first, "text", "")

    return extract
