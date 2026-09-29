from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.api.routes import auth, calculations, files, inputs, layouts, projects
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging

configure_logging(debug=settings.DEBUG)

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "API/service layer around the existing Solar PV Layout Generator engineering "
        "pipeline (core/*). This backend never re-implements capacity, geometry, "
        "packing, grouping, or DXF/DWG logic -- see app/pipeline/adapter.py."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response


app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,  # never "*" in production (spec 28)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(inputs.router)
app.include_router(calculations.router)
app.include_router(layouts.router)
app.include_router(layouts.jobs_router)
app.include_router(files.router)
app.include_router(files.outputs_router)


@app.get("/health", tags=["health"], summary="Liveness check")
def health():
    return {"success": True, "status": "ok", "app": settings.APP_NAME, "env": settings.APP_ENV}
