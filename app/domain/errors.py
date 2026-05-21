"""Domain exceptions — business-rule failures only.

These are distinct from infrastructure exceptions (httpx timeouts, SQLAlchemy errors, etc.).
A single FastAPI exception handler in main.py maps each domain exception to its HTTP status.
Infrastructure exceptions bubble up as 500 with a sanitised message and request_id.
"""


class NotFoundError(Exception):
    def __init__(self, resource: str, id: str) -> None:
        self.resource = resource
        self.id = id
        super().__init__(f"{resource} '{id}' not found")


class PermissionDenied(Exception):
    def __init__(self, reason: str = "Insufficient permissions") -> None:
        super().__init__(reason)


class ToolFailure(Exception):
    def __init__(self, tool: str, reason: str) -> None:
        self.tool = tool
        self.reason = reason
        super().__init__(f"Tool '{tool}' failed: {reason}")


class WidgetOriginNotAllowed(Exception):
    def __init__(self, origin: str, widget_id: str) -> None:
        self.origin = origin
        self.widget_id = widget_id
        super().__init__(f"Origin '{origin}' is not allowed for widget '{widget_id}'")


class InvalidRequest(Exception):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
