# main.py
from identity_service.routes.admin import admin_router
from shared.config import shared_settings
if shared_settings.K8S_NAMESPACE != "":
    import pyroscope
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from prometheus_fastapi_instrumentator import Instrumentator

    pyroscope.configure(
        application_name="bible-service",
        server_address="http://phlare.monitoring.svc.cluster.local:4100"
    )
    trace.set_tracer_provider(TracerProvider())
    otlp_exporter = OTLPSpanExporter(
        endpoint="tempo.monitoring.svc.cluster.local:4317",  # OTLP gRPC port by default
        insecure=True  # skip TLS verification inside the cluster
    )
    span_processor = BatchSpanProcessor(otlp_exporter)
    trace.get_tracer_provider().add_span_processor(span_processor)

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from shared.db_manager import close_engine
from fastapi_events.handlers.local import local_handler
from fastapi_events.middleware import EventHandlerASGIMiddleware
from fastapi.middleware.cors import CORSMiddleware

######### Rate Limiter#######
from slowapi import Limiter
from slowapi.util import get_remote_address

from identity_service.config import settings
######### Rate Limiter#######


from identity_service.routes.auth import auth_router
from identity_service.routes.contact_us import contact_router
from identity_service.routes.frontend_errors import error_router
from identity_service.routes.general import general_router
from identity_service.routes.profile import profile_router
from identity_service.utils.cronjobs import start_cron_jobs
from shared.config import add_origins_to_cors
from shared.enums import MicroServiceName
from shared.openapi_customization import inject_locale_header
from shared.ts_ms.ms_manager import MsManager
from shared.utils.global_store import set_request
from shared.utils.logger import TsLogger
from shared.k8s_log_proxy import log_router

logger = TsLogger(__name__)

# if settings.ENVIRONMENT == 'local':
#     try:
#         import pydevd
#
#         logger.info(f"Local Debugging enabled for ts-core-service on port {settings.LOCAL_DEBUG_PORT}")
#
#         if settings.LOCAL_DEBUG_PORT:
#             debug_port = int(settings.LOCAL_DEBUG_PORT)
#         else:
#             debug_port = 5691
#
#         pydevd.settrace(
#             # 'host.docker.internal',
#             '192.168.68.109',
#             port=debug_port,  # Ensure it is converted to an integer
#             stdoutToServer=True,
#             stderrToServer=True,
#             suspend=False
#         )
#     except Exception as e:
#         logger.error(f"Failed to enable local debugging: {e}")

try:
    microservices = MsManager()
    add_origins_to_cors(microservices)
    identity_service = microservices.get_service(MicroServiceName.IDENTITY_SERVICE.snake())
    if not identity_service:
        raise Exception("Identity service not found in microservices")
    identity_service_root_path = ''
    if not identity_service.local_development_url:
        identity_service_root_path = shared_settings.API_V1_STR + microservices.get_service_url_prefix(
            "identity_service")
except Exception as e:
    logger.error(f"Error initializing Microservices: {e}")
    exit(1)


# FastAPI lifespan event
@asynccontextmanager
async def lifespan(application: FastAPI):
    try:
        start_cron_jobs()
        yield
    finally:
        await close_engine()


common_args = {
    "lifespan": lifespan,
    "title": "TheoSumma Platform - Identity Service",
    "description": "TheoSumma Platform API - Identity Service",
    "version": settings.APP_VERSION,
    "root_path": identity_service_root_path,
}

common_args.update({
    "openapi_url": "/openapi.json" if shared_settings.ENVIRONMENT != 'production' else "",
    "docs_url": "/docs" if shared_settings.ENVIRONMENT != 'production' else "",
})

app = FastAPI(**common_args)
if shared_settings.ALLOW_MONITORING:
    Instrumentator().instrument(app).expose(app)
    FastAPIInstrumentor.instrument_app(app)

############Defined the rate limit middleware##########

limiter = Limiter(key_func=get_remote_address)

app.state.limiter = limiter  # type: ignore[attr-defined]

# Add exception handler for rate limit exceeded errors (I can run this or the custom one's)
# app.add_exception_handler(Exception, _rate_limit_exceeded_handler)

# Apply global rate limit middleware
# TODO: the rate limit should be only on login and registration endpoints
# @app.middleware("http")
# @limiter.limit(settings.RATE_LIMIT)  # Global: 10 requests per 15 minutes per IP
# async def global_rate_limit(request: Request, call_next):
#     return await call_next(request)

if shared_settings.ENVIRONMENT == 'production':
    cors = shared_settings.BACKEND_CORS_ORIGINS
else:
    cors = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:63342",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8021",
        "http://127.0.0.1:8022",
        "http://127.0.0.1:8023",
        "http://127.0.0.1:8024",
        "http://127.0.0.1:8025",
        "http://127.0.0.1:8026",
        "http://127.0.0.1:8027",
        "leh-dev.theosumma.com",
        'hyper-bay-local.vercel.app',
        'https://hyper-bay-local.vercel.app',
    ]

    if identity_service.local_development_url:
        ss = microservices.get_service(MicroServiceName.SUBSCRIPTION_SERVICE.snake())
        cos = microservices.get_service(MicroServiceName.CORE_SERVICE.snake())
        cs = microservices.get_service(MicroServiceName.COMMUNITY_SERVICE.snake())
        bs = microservices.get_service(MicroServiceName.BIBLE_SERVICE.snake())
        pdfs = microservices.get_service(MicroServiceName.DOC_CHATTING_SERVICE.snake())
        cors.extend([
            identity_service.local_development_url,
            ss.local_development_url,
            cos.local_development_url,
            cs.local_development_url,
            bs.local_development_url,
            pdfs.local_development_url,
        ])
    inject_locale_header(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors,  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)
app.add_middleware(EventHandlerASGIMiddleware, handlers=[local_handler])


@app.middleware("http")
async def set_global_data(request: Request, call_next):
    # Set request data in the global storage
    set_request(request)
    response = await call_next(request)
    response.headers["X-Robots-Tag"] = "noindex, nofollow"  # Add the X-Robots-Tag header to disallow indexing
    return response


@app.get("/")
async def root():
    return {
        "status": settings.APP_STATUS,
        "version": settings.APP_VERSION,
    }

if log_router:
    app.include_router(log_router, prefix="/internal")

@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "identity-service running"}


app.include_router(router=general_router)
app.include_router(router=auth_router)
app.include_router(router=profile_router)
app.include_router(router=contact_router)
app.include_router(router=error_router)
app.include_router(router=admin_router)
