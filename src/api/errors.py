import logging
from typing import Dict, Any, Union
from fastapi import Request, FastAPI
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

class PPTSystemException(Exception):
    """Base exception for PPT retrieval system."""
    def __init__(self, message: str, status_code: int = 500, details: Dict[str, Any] = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

class VisionProcessingError(PPTSystemException):
    def __init__(self, message: str, details: Dict[str, Any] = None):
        super().__init__(message, status_code=500, details=details)

class ReasoningError(PPTSystemException):
    def __init__(self, message: str, details: Dict[str, Any] = None):
        super().__init__(message, status_code=500, details=details)

def setup_exception_handlers(app: FastAPI):
    @app.exception_handler(PPTSystemException)
    async def ppt_system_exception_handler(request: Request, exc: PPTSystemException):
        logger.error(f"System Error: {exc.message}, Details: {exc.details}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.__class__.__name__,
                "message": exc.message,
                "details": exc.details
            }
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "HTTPException",
                "message": exc.detail
            }
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.warning(f"Validation error on {request.url}: {exc.errors()}")
        return JSONResponse(
            status_code=422,
            content={
                "error": "ValidationError",
                "message": "Input format is invalid",
                "details": exc.errors()
            }
        )
