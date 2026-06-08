"""OTel tracing setup — HTTP exporter (Render-compatible) + SimpleSpanProcessor."""
import base64
import logging

_log = logging.getLogger(__name__)


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

    # Build Basic-auth header required by Grafana Cloud OTLP endpoint
    raw = f"{settings.grafana_instance_id}:{settings.grafana_otlp_token}"
    b64 = base64.b64encode(raw.encode()).decode()
    headers = {"Authorization": f"Basic {b64}"}

    resource = Resource.create(
        {
            "service.name": getattr(settings, "service_name", "collection-assistant"),
            "deployment.environment": getattr(settings, "environment", "production"),
        }
    )

    provider = TracerProvider(resource=resource)

    exporter = OTLPSpanExporter(
        endpoint=f"{settings.grafana_otlp_endpoint.rstrip('/')}/v1/traces",
        headers=headers,
    )
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    trace.set_tracer_provider(provider)

    _log.info(
        "OTel tracing initialised",
        extra={"endpoint": settings.grafana_otlp_endpoint},
    )
    return trace.get_tracer("collection_assistant")
