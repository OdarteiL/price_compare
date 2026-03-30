"""
OpenTelemetry setup — traces, metrics, and logs exported via OTLP.
Also exposes a Prometheus metrics endpoint for scraping.
"""
import logging
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.sampling import ParentBasedTraceIdRatio
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from prometheus_client import start_http_server

from app.core.config import settings

logger = logging.getLogger(__name__)


def setup_telemetry(app=None) -> None:
    resource = Resource.create({
        SERVICE_NAME: settings.otel_service_name,
        SERVICE_VERSION: settings.app_version,
        "deployment.environment": settings.otel_environment,
    })

    _setup_tracing(resource)
    _setup_metrics(resource)
    _instrument_libraries(app)

    logger.info("OpenTelemetry initialized", extra={
        "service": settings.otel_service_name,
        "endpoint": settings.otel_exporter_otlp_endpoint,
    })


def _setup_tracing(resource: Resource) -> None:
    otlp_exporter = OTLPSpanExporter(
        endpoint=settings.otel_exporter_otlp_endpoint,
        insecure=True,
    )
    sampler = ParentBasedTraceIdRatio(1.0 if settings.debug else 0.1)
    provider = TracerProvider(resource=resource, sampler=sampler)
    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    trace.set_tracer_provider(provider)


def _setup_metrics(resource: Resource) -> None:
    # OTLP export
    otlp_metric_exporter = OTLPMetricExporter(
        endpoint=settings.otel_exporter_otlp_endpoint,
        insecure=True,
    )
    otlp_reader = PeriodicExportingMetricReader(otlp_metric_exporter, export_interval_millis=30_000)

    # Prometheus scrape endpoint on port 9090
    prometheus_reader = PrometheusMetricReader()
    try:
        start_http_server(port=9090, addr="0.0.0.0")
    except OSError:
        pass  # Already started in another worker

    provider = MeterProvider(
        resource=resource,
        metric_readers=[otlp_reader, prometheus_reader],
    )
    metrics.set_meter_provider(provider)


def _instrument_libraries(app) -> None:
    if app:
        FastAPIInstrumentor.instrument_app(app, excluded_urls="health,metrics")
    RedisInstrumentor().instrument()
    AioHttpClientInstrumentor().instrument()
    # SQLAlchemy is instrumented after engine creation via instrument_engine()


def instrument_sqlalchemy_engine(engine) -> None:
    SQLAlchemyInstrumentor().instrument(engine=engine)


def get_tracer(name: str = __name__):
    return trace.get_tracer(name)


def get_meter(name: str = __name__):
    return metrics.get_meter(name)
