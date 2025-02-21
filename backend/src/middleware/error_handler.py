from fastapi import Request, status
from fastapi.responses import JSONResponse
from ..utils.exceptions import TranscriboError
from ..models.base import ErrorResponse
from ..utils.logging import get_logger
import sys
import traceback

logger = get_logger(__name__)

async def error_handler_middleware(request: Request, call_next):
    """Global error handling middleware"""
    try:
        return await call_next(request)
        
    except TranscriboError as e:
        # Our custom exceptions already have proper formatting
        logger.warning(
            f"Request failed: {e.detail['message']}",
            extra={
                "error_code": e.detail["code"],
                "details": e.detail.get("details"),
                "status_code": e.status_code,
                "path": request.url.path
            }
        )
        return JSONResponse(
            status_code=e.status_code,
            content=e.detail
        )
        
    except Exception as e:
        # Unexpected errors get converted to internal server error
        exc_type, exc_value, exc_traceback = sys.exc_info()
        
        # Log full traceback for unexpected errors
        logger.error(
            f"Unexpected error: {str(e)}",
            extra={
                "error_type": exc_type.__name__,
                "traceback": "".join(traceback.format_tb(exc_traceback)),
                "path": request.url.path
            }
        )
        
        # Return sanitized error response
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                code="INTERNAL_ERROR",
                message="An unexpected error occurred",
                details={
                    "type": exc_type.__name__
                } if not request.app.debug else {
                    "type": exc_type.__name__,
                    "message": str(e),
                    "traceback": "".join(traceback.format_tb(exc_traceback))
                }
            ).dict()
        )
