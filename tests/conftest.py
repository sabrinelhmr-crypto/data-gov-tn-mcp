# Fixtures pytest

import pytest


def pytest_configure(config: "pytest.Config") -> None:
    config.addinivalue_line("markers", "asyncio: mark test as async")
    config.option.asyncio_mode = "auto"
