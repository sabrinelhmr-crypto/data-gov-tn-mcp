import logging

from pythonjsonlogger.json import JsonFormatter

from config import settings


def setup_logging() -> None:
    handler = logging.StreamHandler()
    formatter = JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.setLevel(settings.LOG_LEVEL)
    root.addHandler(handler)
