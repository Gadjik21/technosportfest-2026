from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.errors import install_error_handlers
from app.modules.competitions.router import router as competitions_router
from app.modules.content.router import router as content_router
from app.modules.identity.profile import router as profile_router
from app.modules.identity.router import router as auth_router
from app.modules.identity.security import COOKIE_NAME, decode_token
from app.modules.results.router import router as results_router


def create_app() -> FastAPI:
    app = FastAPI(title="ТехноСпортФест 2026", version="0.1.0")
    install_error_handlers(app)

    @app.middleware("http")
    async def auth_context_and_origin(request: Request, call_next):
        if request.url.path.startswith("/api/v1/"):
            if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
                origin = request.headers.get("origin")
                if origin not in get_settings().allowed_origins:
                    return JSONResponse(
                        status_code=403,
                        content={"code": "ORIGIN_INVALID", "message": "Недопустимый Origin запроса."},
                    )
            request.state.principal = decode_token(request.cookies.get(COOKIE_NAME))
        return await call_next(request)

    @app.get("/health", include_in_schema=False)
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(profile_router, prefix="/api/v1")
    app.include_router(competitions_router, prefix="/api/v1")
    app.include_router(results_router, prefix="/api/v1")
    app.include_router(content_router, prefix="/api/v1")
    return app


app = create_app()
