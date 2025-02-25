from opentelemetry import trace
from opentelemetry import metrics as otel_metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
import os

def setup_telemetry(app):
    """Set up OpenTelemetry instrumentation"""
    resource = Resource.create({"service.name": "frontend"})
    
    # Set up tracing
    tracer_provider = TracerProvider(resource=resource)
    otlp_span_exporter = OTLPSpanExporter(
        endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4318/v1/traces")
    )
    span_processor = BatchSpanProcessor(otlp_span_exporter)
    tracer_provider.add_span_processor(span_processor)
    trace.set_tracer_provider(tracer_provider)

    # Set up metrics with OTLP exporter
    otlp_metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(
            endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4318/v1/metrics")
        ),
        export_interval_millis=10000  # Export every 10 seconds
    )
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[otlp_metric_reader],
        views=[]  # Use default views
    )
    otel_metrics.set_meter_provider(meter_provider)

    # Instrument FastAPI with OpenTelemetry
    FastAPIInstrumentor.instrument_app(app)
