from enum import Enum
from typing import Optional


class ErrorCode(str, Enum):
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
    NETWORK_CONNECTION = "NETWORK_CONNECTION"
    NETWORK_DNS = "NETWORK_DNS"
    NETWORK_SSL = "NETWORK_SSL"
    NETWORK_HTTP_4XX = "NETWORK_HTTP_4XX"
    NETWORK_HTTP_5XX = "NETWORK_HTTP_5XX"
    NETWORK_RATE_LIMIT = "NETWORK_RATE_LIMIT"

    PARSE_INVALID_URI = "PARSE_INVALID_URI"
    PARSE_INVALID_BASE64 = "PARSE_INVALID_BASE64"
    PARSE_INVALID_JSON = "PARSE_INVALID_JSON"
    PARSE_INVALID_YAML = "PARSE_INVALID_YAML"
    PARSE_UNSUPPORTED_PROTOCOL = "PARSE_UNSUPPORTED_PROTOCOL"

    DB_INIT_FAILED = "DB_INIT_FAILED"
    DB_WRITE_FAILED = "DB_WRITE_FAILED"
    DB_READ_FAILED = "DB_READ_FAILED"
    DB_CORRUPTED = "DB_CORRUPTED"

    FILE_READ_FAILED = "FILE_READ_FAILED"
    FILE_WRITE_FAILED = "FILE_WRITE_FAILED"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    FILE_DIALOG_UNAVAILABLE = "FILE_DIALOG_UNAVAILABLE"

    SOURCE_DISCOVERY_FAILED = "SOURCE_DISCOVERY_FAILED"
    SOURCE_FETCH_FAILED = "SOURCE_FETCH_FAILED"

    CONFIG_EMPTY = "CONFIG_EMPTY"
    CONFIG_DUPLICATE = "CONFIG_DUPLICATE"
    CONFIG_EXPIRED = "CONFIG_EXPIRED"
    CONFIG_TOO_LONG = "CONFIG_TOO_LONG"

    EXPORT_NO_DATA = "EXPORT_NO_DATA"
    EXPORT_UNSUPPORTED = "EXPORT_UNSUPPORTED"

    QR_GENERATION_FAILED = "QR_GENERATION_FAILED"

    GENERAL_UNKNOWN = "GENERAL_UNKNOWN"


class AppError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        detail: str,
        operation: Optional[str] = None,
        cause: Optional[Exception] = None,
    ):
        self.code = code
        self.detail = detail
        self.operation = operation
        self.cause = cause
        super().__init__(self.detail)

    def to_dict(self) -> dict:
        result = {"code": self.code.value, "detail": self.detail}
        if self.operation:
            result["operation"] = self.operation
        return result

    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict())

    def __repr__(self) -> str:
        return f"AppError(code={self.code!r}, detail={self.detail!r})"


def network_timeout(url: str, timeout: int) -> AppError:
    return AppError(ErrorCode.NETWORK_TIMEOUT, f"Request to {url} timed out after {timeout}s")


def network_connection(url: str, reason: str) -> AppError:
    return AppError(ErrorCode.NETWORK_CONNECTION, f"Cannot connect to {url}: {reason}")


def network_http(url: str, status: int) -> AppError:
    if 400 <= status < 500:
        code = ErrorCode.NETWORK_HTTP_4XX
    else:
        code = ErrorCode.NETWORK_HTTP_5XX
    return AppError(code, f"HTTP {status} from {url}")


def parse_invalid_uri(line: str, protocol: str) -> AppError:
    return AppError(ErrorCode.PARSE_INVALID_URI, f"Invalid {protocol} URI: {line[:80]}")


def parse_unsupported(line: str) -> AppError:
    return AppError(ErrorCode.PARSE_UNSUPPORTED_PROTOCOL, f"Unsupported protocol in: {line[:80]}")


def db_error(detail: str, cause: Optional[Exception] = None) -> AppError:
    return AppError(ErrorCode.DB_INIT_FAILED, detail, cause=cause)


def file_error(filepath: str, detail: str) -> AppError:
    return AppError(ErrorCode.FILE_READ_FAILED, f"Cannot read {filepath}: {detail}")


def export_no_data() -> AppError:
    return AppError(ErrorCode.EXPORT_NO_DATA, "No configs to export")
