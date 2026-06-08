"""Structured logging configuration using structlog with JSON renderer for Loki ingestion."""
import logging
import logging.config
import sys


def configure_structlog() -> None:
    """Configure structlog with JSON output, contextvars merging, and stdlib integration."""
    try:
        import structlog

        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.stdlib.add_log_level,
                structlog.stdlib.add_logger_name,
                structlog.processors.TimeStamper(fmt="iso", utc=True),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
            cache_logger_on_first_use=True,
        )

        # Route stdlib logging through structlog so FastAPI/uvicorn logs are also JSON
        logging.config.dictConfig(
            {
                "version": 1,
                "disable_existing_loggers": False,
                "formatters": {
                    "structlog_plain": {
                        "()": structlog.stdlib.ProcessorFormatter,
                        "processors": [
                            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                            structlog.processors.JSONRenderer(),
                        ],
                        "foreign_pre_chain": [
                            structlog.contextvars.merge_contextvars,
                            structlog.stdlib.add_log_level,
                            structlog.stdlib.add_logger_name,
                            structlog.processors.TimeStamper(fmt="iso", utc=True),
                        ],
                    },
                },
                "handlers": {
                    "default": {
                        "class": "logging.StreamHandler",
                        "stream": "ext://sys.stdout",
                        "formatter": "structlog_plain",
                    },
                },
                "root": {
                    "handlers": ["default"],
                    "level": "INFO",
                },
                "loggers": {
                    "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
                    "uvicorn.error": {"handlers": ["default"], "level": "INFO", "propagate": False},
                    "uvicorn.access": {"handlers": ["default"], "level": "INFO", "propagate": False},
                    "fastapi": {"handlers": ["default"], "level": "INFO", "propagate": False},
                },
            }
        )
    except ImportError:
        # structlog not installed — fall back to plain stdlib logging
        logging.basicConfig(
            stream=sys.stdout,
            level=logging.INFO,
            format='{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
        )


def bind_workflow_context(workflow_id: str, customer_id: str) -> None:
    """Bind per-request context vars so every log line carries workflow/customer IDs."""
    try:
        import structlog
        structlog.contextvars.bind_contextvars(
            workflow_id=workflow_id,
            customer_id=customer_id,
        )
    except ImportError:
        pass


def clear_workflow_context() -> None:
    """Clear context vars at end of request to avoid leaking into the next request."""
    try:
        import structlog
        structlog.contextvars.clear_contextvars()
    except ImportError:
        pass
