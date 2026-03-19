import os
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI

from apps.api.config import settings
from apps.api.db import init_db
from apps.api.routes.admin import router as admin_router, public_router as admin_public_router
from apps.api.routes.health import router as health_router
from apps.api.routes.internal import router as internal_router
from apps.api.routes.leads import router as leads_router, public_router as leads_public_router

# --- Sentry ---
_sentry_dsn = os.getenv("SENTRY_DSN", "")
if _sentry_dsn:
    sentry_sdk.init(
        dsn=_sentry_dsn,
        environment=settings.app_env,
        traces_sample_rate=0,
        send_default_pii=False,
    )

# --- OpenTelemetry ---
_otel_enabled = os.getenv("OTEL_ENABLED", "").lower() in ("1", "true", "yes")
if _otel_enabled:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.resources import Resource

    resource = Resource.create({"service.name": os.getenv("OTEL_SERVICE_NAME", "openclaw-api")})
    provider = TracerProvider(resource=resource)

    _otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if _otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=_otlp_endpoint)))
    else:
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

if _otel_enabled:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    FastAPIInstrumentor.instrument_app(app)

app.include_router(health_router)
app.include_router(admin_public_router)
app.include_router(leads_public_router)
app.include_router(internal_router)
app.include_router(admin_router)
app.include_router(leads_router)