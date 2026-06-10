"""Custom exception classes for the application."""


class AIBrowserException(Exception):
    """Base exception for all application errors."""


class TaskParsingError(AIBrowserException):
    """Failed to parse user task into browser steps."""


class BrowserExecutionError(AIBrowserException):
    """A browser operation failed after all retries."""


class SecurityViolationError(AIBrowserException):
    """A generated step was blocked by the security module."""


class ClaudeAPIError(AIBrowserException):
    """Claude API call failed."""


class RedisConnectionError(AIBrowserException):
    """Redis connection or operation failed."""


class TaskTimeoutError(AIBrowserException):
    """Task execution exceeded the configured timeout."""


class TaskNotFoundError(AIBrowserException):
    """Requested task ID not found in storage."""
