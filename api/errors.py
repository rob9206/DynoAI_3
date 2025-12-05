"""
DynoAI Centralized Error Handling.

Provides standardized error responses and exception handling for the Flask API.
"""

import logging
import traceback
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple, TypeVar

from flask import Flask, Response, jsonify, request

logger = logging.getLogger(__name__)

# Type variable for decorated functions
F = TypeVar("F", bound=Callable[..., Any])


class APIError(Exception):
    """Base exception for API errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or f"ERR_{status_code}"
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to API response dictionary."""
        response = {
            "error": {
                "code": self.error_code,
                "message": self.message,
            }
        }
        if self.details:
            response["error"]["details"] = self.details
        return response


class ValidationError(APIError):
    """Raised when request validation fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=400,
            error_code="VALIDATION_ERROR",
            details=details,
        )


class NotFoundError(APIError):
    """Raised when a requested resource is not found."""

    def __init__(
        self,
        resource: str,
        identifier: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        message = f"{resource} not found"
        if identifier:
            message = f"{resource} '{identifier}' not found"
        super().__init__(
            message=message,
            status_code=404,
            error_code="NOT_FOUND",
            details=details or {"resource": resource, "identifier": identifier},
        )


class FileNotAllowedError(APIError):
    """Raised when file type is not allowed."""

    def __init__(self, filename: str, allowed_types: Optional[list] = None):
        details = {"filename": filename}
        if allowed_types:
            details["allowed_types"] = allowed_types
        super().__init__(
            message=f"File type not allowed: {filename}",
            status_code=400,
            error_code="FILE_TYPE_NOT_ALLOWED",
            details=details,
        )


class AnalysisError(APIError):
    """Raised when analysis fails."""

    def __init__(self, message: str, stage: Optional[str] = None):
        super().__init__(
            message=f"Analysis failed: {message}",
            status_code=500,
            error_code="ANALYSIS_ERROR",
            details={"stage": stage} if stage else {},
        )


class JetstreamError(APIError):
    """Raised when Jetstream integration fails."""

    def __init__(self, message: str, operation: Optional[str] = None):
        super().__init__(
            message=f"Jetstream error: {message}",
            status_code=502,
            error_code="JETSTREAM_ERROR",
            details={"operation": operation} if operation else {},
        )


class ConfigurationError(APIError):
    """Raised when configuration is invalid."""

    def __init__(self, message: str, setting: Optional[str] = None):
        super().__init__(
            message=f"Configuration error: {message}",
            status_code=500,
            error_code="CONFIGURATION_ERROR",
            details={"setting": setting} if setting else {},
        )


def error_response(
    message: str,
    status_code: int = 500,
    error_code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Tuple[Response, int]:
    """Create a standardized error response."""
    response = {
        "error": {
            "code": error_code or f"ERR_{status_code}",
            "message": message,
        }
    }
    if details:
        response["error"]["details"] = details
    return jsonify(response), status_code


def handle_api_error(error: APIError) -> Tuple[Response, int]:
    """Handle APIError exceptions."""
    logger.warning(
        f"API Error [{error.error_code}]: {error.message}",
        extra={"details": error.details},
    )
    return jsonify(error.to_dict()), error.status_code


def handle_exception(error: Exception) -> Tuple[Response, int]:
    """Handle unexpected exceptions."""
    logger.error(
        f"Unhandled exception: {str(error)}",
        exc_info=True,
    )
    
    # In debug mode, include traceback
    from flask import current_app
    details = {}
    if current_app.debug:
        details["traceback"] = traceback.format_exc()
    
    return error_response(
        message="An unexpected error occurred",
        status_code=500,
        error_code="INTERNAL_ERROR",
        details=details if details else None,
    )


def register_error_handlers(app: Flask) -> None:
    """Register error handlers with Flask app."""
    
    @app.errorhandler(APIError)
    def api_error_handler(error: APIError) -> Tuple[Response, int]:
        return handle_api_error(error)
    
    @app.errorhandler(400)
    def bad_request_handler(error: Exception) -> Tuple[Response, int]:
        return error_response(
            message=str(error.description) if hasattr(error, "description") else "Bad request",
            status_code=400,
            error_code="BAD_REQUEST",
        )
    
    @app.errorhandler(404)
    def not_found_handler(error: Exception) -> Tuple[Response, int]:
        return error_response(
            message="Resource not found",
            status_code=404,
            error_code="NOT_FOUND",
            details={"path": request.path},
        )
    
    @app.errorhandler(405)
    def method_not_allowed_handler(error: Exception) -> Tuple[Response, int]:
        return error_response(
            message=f"Method {request.method} not allowed for {request.path}",
            status_code=405,
            error_code="METHOD_NOT_ALLOWED",
        )
    
    @app.errorhandler(413)
    def request_too_large_handler(error: Exception) -> Tuple[Response, int]:
        return error_response(
            message="Request entity too large",
            status_code=413,
            error_code="REQUEST_TOO_LARGE",
        )
    
    @app.errorhandler(500)
    def internal_error_handler(error: Exception) -> Tuple[Response, int]:
        return handle_exception(error)
    
    @app.errorhandler(Exception)
    def generic_error_handler(error: Exception) -> Tuple[Response, int]:
        # Don't catch HTTPException subclasses - let Flask handle them
        from werkzeug.exceptions import HTTPException
        if isinstance(error, HTTPException):
            return error_response(
                message=error.description or str(error),
                status_code=error.code or 500,
            )
        return handle_exception(error)


def with_error_handling(f: F) -> F:
    """
    Decorator for route handlers with standardized error handling.
    
    Usage:
        @app.route("/api/example")
        @with_error_handling
        def example_route():
            # Your code here
            pass
    """
    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        try:
            return f(*args, **kwargs)
        except APIError:
            raise  # Let the error handler deal with it
        except FileNotFoundError as e:
            raise NotFoundError(resource="File", identifier=str(e))
        except ValueError as e:
            raise ValidationError(message=str(e))
        except Exception as e:
            logger.error(f"Unexpected error in {f.__name__}: {e}", exc_info=True)
            raise APIError(
                message=str(e),
                status_code=500,
                error_code="UNEXPECTED_ERROR",
            )
    return decorated  # type: ignore

