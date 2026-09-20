import logging
from src.config import LOG_LEVEL


def configure_logging():
    level = getattr(logging, LOG_LEVEL, None)
    if not isinstance(level, int):
        raise RuntimeError(f"LOG_LEVEL is invalid: {LOG_LEVEL}")
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
