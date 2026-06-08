"""OTel tracing setup — HTTP exporter (Render-compatible) + SimpleSpanProcessor."""
import base64
import logging

_log = logging.getLogger(__name__)


def _build_auth_headers(settings) -> dict:
    """Return the correct auth headers for the configured OTLP provider."""
    provider = getattr(settings, "otlp_provider", "newrelic").lower()
    token = settings.otlp_token
    if provider == "grafana":
        instance_id = getattr(settings, "grafana_instance_id", "")
        b64 = base64.b64encode(f"{instance_id}:{token}".encode()).decode()
        return {"Authorization": f"Basic {b64}"}
    # New Relic (default): api-key header
    return {"api-key": token}


def setup_tracing(settings):
    """
    Initialise a TracerProvider with:
    - OTLPSpanExporter over HTTP (opentelemetry-exporter-otlp-proto-http)
    - SimpleSpanProcessor — avoids data loss when Render sleeps the dyno
    - Resource attributes: service.name, deployment.environment

    Returns a Tracer instance, or None if OTel packages are missing.
    """
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    except ImportError:
        _log.warning("OTel tracing packages not installed — tracing disabled")
        return None

    resource = Resource.create(
        {
            "service.name": getattr(settings, "service_name", "collection-assistant"),
            "deployment.environment": getattr(settings, "environment", "production"),
        }
    )

    provider = TracerProvider(resource=resource)

    exporter = OTLPSpanExporter(
        endpoint=f"{settings.otlp_endpoint.rstrip('/')}/v1/traces",
        headers=_build_auth_headers(settings),
    )
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    trace.set_tracer_provider(provider)

    _log.info("OTel tracing initialised", extra={"endpoint": settings.otlp_endpoint})
    return trace.get_tracer("collection_assistant")
