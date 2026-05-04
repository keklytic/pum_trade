import logging
import os
import sys

try:
    import logging_loki
    _loki_available = True
except ImportError:
    _loki_available = False


_LOKI_URL = os.environ.get("LOKI_URL")
_LOKI_USERNAME = os.environ.get("LOKI_USERNAME")
_LOKI_PASSWORD = os.environ.get("LOKI_PASSWORD")
_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
_ENV = os.environ.get("ENV", "prod")
_FUNCTION_NAME = os.environ.get("AWS_LAMBDA_FUNCTION_NAME", "local")


class _JsonFormatter(logging.Formatter):
    def format(self, record):
        import json, traceback
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "function": _FUNCTION_NAME,
            "env": _ENV,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = traceback.format_exception(*record.exc_info)
        return json.dumps(payload)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(_LOG_LEVEL)

    # Always log structured JSON to stdout (CloudWatch fallback / local dev)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(_JsonFormatter())
    logger.addHandler(stdout_handler)

    # Push to Loki directly when env vars are present
    if _loki_available and _LOKI_URL:
        auth = (_LOKI_USERNAME, _LOKI_PASSWORD) if _LOKI_USERNAME and _LOKI_PASSWORD else None
        loki_handler = logging_loki.LokiHandler(
            url=_LOKI_URL,
            tags={"service": "pum-trade", "function": _FUNCTION_NAME, "env": _ENV},
            auth=auth,
            version="1",
        )
        loki_handler.setLevel(_LOG_LEVEL)
        logger.addHandler(loki_handler)

    logger.propagate = False
    return logger
