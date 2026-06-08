"""Observability bootstrap — metrics, tracing, structured logging.

Usage
-----
Call ``setup_observability(settings)`` once at application startup (e.g. in
FastAPI lifespan).  Everything is guarded against missing OTel packages so the
app continues to work in environments where the optional deps are not installed.

    from collection_assistant.observability import setup_observability, get_tracer, get_meter

    setup_observability(settings)          # idempotent
    tracer = get_tracer()                  # may be None if OTel not configured
    meter  = get_meter()                   # may be None if OTel not configured
"""
import logging
from typing import Optional

_log = logging.getLogger(__name__)

# Module-level singletons so callers can import get_tracer/get_meter anywhere
_tracer = None
_meter: Optional[object] = None

_setup_done = False


def get_tracer():
    """Return the OTel Tracer, or None when OTel is not configured."""
    return _tracer


def get_meter():
    """Return the OTel Meter, or None when OTel is not configured."""
    return _meter


def setup_observability(settings) -> None:
    """Configure OTel metrics + traces + structlog.  No-op if packages missing.

    This function is idempotent — subsequent calls after the first are ignored.

    Parameters
    ----------
    settings:
        The application ``Settings`` instance from ``collection_assistant.config``.
        Required attributes (all optional in Settings, default to ``""``):
        - ``grafana_otlp_endpoint`` — base URL of the Grafana Cloud OTLP endpoint
        - ``grafana_otlp_token``    — API key / token
        - ``grafana_instance_id``   — numeric Grafana stack / instance ID (used for
                                      Basic-auth header construction)
        - ``service_name``          — reported as ``service.name`` resource attr
                                      (defaults to ``"collection-assistant"``)
        - ``environment``           — reported as ``deployment.environment``
                                      (defaults to ``"production"``)
    """
    global _tracer, _meter, _setup_done

    if _setup_done:
        return
    _setup_done = True

    # 1. Structured logging — always attempt (structlog is in core deps)
    _setup_logging()

    # 2. OTel traces + metrics — only if endpoint + token are provided
    endpoint = getattr(settings, "grafana_otlp_endpoint", "") or ""
    token = getattr(settings, "grafana_otlp_token", "") or ""

    if not endpoint or not token:
        _log.info(
            "Observability: OTLP not configured — metrics/traces disabled. "
            "Set GRAFANA_OTLP_ENDPOINT and GRAFANA_OTLP_TOKEN to enable."
        )
        return

    _tracer = _setup_tracing(settings)
    _meter = _setup_metrics(settings)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _setup_logging() -> None:
    """Delegate to logging_config; silently degrade if structlog unavailable."""
    try:
        from collection_assistant.observability.logging_config import configure_structlog
        configure_structlog()
        _log.debug("Structured JSON logging configured via structlog")
    except Exception as exc:  # pragma: no cover
        logging.basicConfig(level=logging.INFO)
        logging.getLogger(__name__).warning(
            "structlog configuration failed — using stdlib logging: %s", exc
        )


def _setup_tracing(settings):
    """Initialise OTel tracing.  Returns a Tracer or None."""
    try:
        from collection_assistant.observability.tracing import setup_tracing
        tracer = setup_tracing(settings)
        return tracer
    except ImportError:
        _log.warning("OTel tracing packages not available — tracing disabled")
        return None
    except Exception as exc:
        _log.warning("OTel tracing setup failed: %s", exc)
        return None


def _setup_metrics(settings):
    """Initialise OTel metrics.  Returns a Meter or None."""
    try:
        import base64

        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter

        raw = f"{getattr(settings, 'grafana_instance_id', '')}:{settings.grafana_otlp_token}"
        b64 = base64.b64encode(raw.encode()).decode()
        headers = {"Authorization": f"Basic {b64}"}

        resource = Resource.create(
            {
                "service.name": getattr(settings, "service_name", "collection-assistant"),
                "deployment.environment": getattr(settings, "environment", "production"),
            }
        )

        exporter = OTLPMetricExporter(
            endpoint=f"{settings.grafana_otlp_endpoint.rstrip('/')}/v1/metrics",
            headers=headers,
        )

        reader = PeriodicExportingMetricReader(exporter, export_interval_millis=60_000)
        provider = MeterProvider(resource=resource, metric_readers=[reader])

        from opentelemetry import metrics as otel_metrics
        otel_metrics.set_meter_provider(provider)

        meter = otel_metrics.get_meter("collection_assistant")

        # Populate the instrument singletons in metrics.py
        from collection_assistant.observability.metrics import create_instruments
        create_instruments(meter)

        _log.info(
            "OTel metrics initialised",
            extra={"endpoint": settings.grafana_otlp_endpoint},
        )
        return meter

    except ImportError:
        _log.warning("OTel metrics packages not available — metrics disabled")
        return None
    except Exception as exc:
        _log.warning("OTel metrics setup failed: %s", exc)
        return None
