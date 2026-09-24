from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error(_: Request, error: ApiError) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content={"code": error.code, "message": error.message})

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
        fields = {".".join(map(str, item["loc"])): item["msg"] for item in error.errors()}
        return JSONResponse(
            status_code=422,
            content={"code": "VALIDATION_ERROR", "message": "Проверьте данные запроса.", "fields": fields},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, error: StarletteHTTPException) -> JSONResponse:
        code = "NOT_FOUND" if error.status_code == 404 else "BAD_REQUEST"
        return JSONResponse(status_code=error.status_code, content={"code": code, "message": str(error.detail)})
