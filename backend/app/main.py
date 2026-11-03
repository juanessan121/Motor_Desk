from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text

from . import (
    activity_routes,
    assignment_routes,
    auth_routes,
    catalog_routes,
    config_routes,
    export_routes,
    inspection_routes,
    operations_routes,
    order_routes,
    registry_routes,
    workshop_routes,
)
from .dependencies import Database
from .catalog_review_routes import router as catalog_review_router
from .catalog_browse_routes import router as catalog_browse_router
from .parts_operations_routes import router as parts_operations_router
from .registry_transfer import router as registry_transfer_router
from .notifications import notification_lifespan
from .settings import settings


@asynccontextmanager
async def lifespan(_app):
    async with notification_lifespan():
        yield


production = settings().environment == "production"
app = FastAPI(
    title="MotorDesk API", version="1.0.0", lifespan=lifespan,
    docs_url=None if production else "/docs",
    redoc_url=None if production else "/redoc",
    openapi_url=None if production else "/openapi.json",
)
app.add_middleware(
    CORSMiddleware, allow_origins=settings().cors_origins,
    allow_credentials=False, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Device-Id", "ngrok-skip-browser-warning"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


for router in (
    auth_routes.router,
    registry_routes.router,
    order_routes.router,
    config_routes.router,
    operations_routes.router,
    assignment_routes.router,
    inspection_routes.router,
    workshop_routes.router,
    catalog_routes.router,
    activity_routes.router,
    export_routes.router,
):
    app.include_router(router, prefix="/api/v1")
app.include_router(catalog_review_router, prefix="/api/v1")
app.include_router(catalog_browse_router, prefix="/api/v1")
app.include_router(parts_operations_router, prefix="/api/v1")
app.include_router(registry_transfer_router, prefix="/api/v1")


@app.get("/api/v1/health", tags=["Salud"])
def health(db: Database):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}


@app.get("/{path:path}", include_in_schema=False)
def web(path: str):
    if path.startswith("api/"):
        raise HTTPException(404, "Endpoint no encontrado")
    root = Path(settings().web_directory).resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        raise HTTPException(404)
    if target.is_file():
        # Flutter conserva nombres estables: evitar ejecutar una versión antigua
        # de main.dart.js después de instalar una actualización.
        return FileResponse(target, headers={"Cache-Control": "no-cache"})
    if (root / "index.html").exists():
        return FileResponse(root / "index.html", headers={"Cache-Control": "no-cache"})
    return JSONResponse({"message": "MotorDesk API", "documentation": "/docs", "web": "Compile Flutter Web o use flutter run"})
