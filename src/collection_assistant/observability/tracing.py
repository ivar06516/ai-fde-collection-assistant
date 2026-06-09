"""OTel tracing setup — HTTP exporter (Render-compatible) + BatchSpanProcessor."""
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
    - BatchSpanProcessor — buffers spans and exports in batches for better throughput.
      schedule_delay=5s, export_timeout=10s, max_queue=2048.
    - Resource attributes: service.name, deployment.environment, host.name

    Returns a Tracer instance, or None if OTel packages are missing.
    """
    try:
        import socket

        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    except ImportError:
        _log.warning("OTel tracing packages not installed — tracing disabled")
        return None

    resource = Resource.create(
        {
            "service.name": getattr(settings, "service_name", "collection-assistant"),
            "service.version": "0.1.0",
            "deployment.environment": getattr(settings, "environment", "production"),
            "host.name": socket.gethostname(),
        }
    )

    provider = TracerProvider(resource=resource)

    exporter = OTLPSpanExporter(
        endpoint=f"{settings.otlp_endpoint.rstrip('/')}/v1/traces",
        headers=_build_auth_headers(settings),
    )
    # BatchSpanProcessor: buffers up to 2048 spans, flushes every 5s or when buffer hits 512
    processor = BatchSpanProcessor(
        exporter,
        schedule_delay_millis=5_000,
        export_timeout_millis=10_000,
        max_export_batch_size=512,
        max_queue_size=2_048,
    )
    provider.add_span_processor(processor)

    trace.set_tracer_provider(provider)

    _log.info("OTel tracing initialised", extra={"endpoint": settings.otlp_endpoint})
    return trace.get_tracer("collection_assistant")
