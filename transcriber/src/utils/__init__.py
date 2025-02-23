from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.prometheus import PrometheusMetricExporter
from prometheus_client import start_http_server
import os

def setup_telemetry(app):
    """Set up OpenTelemetry instrumentation"""
    resource = Resource.create({"service.name": "transcriber"})
    
    # Set up tracing
    tracer_provider = TracerProvider(resource=resource)
    otlp_span_exporter = OTLPSpanExporter(
        endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318") + "/v1/traces"
    )
    span_processor = BatchSpanProcessor(otlp_span_exporter)
    tracer_provider.add_span_processor(span_processor)
    trace.set_tracer_provider(tracer_provider)

    # Set up metrics with both OTLP and Prometheus exporters
    otlp_metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(
            endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318") + "/v1/metrics"
        )
    )
    prometheus_exporter = PrometheusMetricExporter()
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[otlp_metric_reader, prometheus_exporter]
    )
    metrics.set_meter_provider(meter_provider)

    # Create a meter for our metrics
    meter = metrics.get_meter_provider().get_meter("transcriber")

    # Instrument FastAPI
    FastAPIInstrumentor.instrument_app(app)
