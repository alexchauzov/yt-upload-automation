"""Unified adapter error types."""
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class AdapterError(Exception):
    """
    Unified error type for all adapter failures.

    Allows adapters to return structured error information without coupling
    domain logic to specific error reasons or external API details.

    Orchestrator will interpret error codes and apply appropriate policy
    (retry, mark as failed, log details, etc).
    """
    code: str
    message: str
    details: Optional[Any] = None

    def __str__(self) -> str:
        if self.details:
            return f"[{self.code}] {self.message} (details: {self.details})"
        return f"[{self.code}] {self.message}"
