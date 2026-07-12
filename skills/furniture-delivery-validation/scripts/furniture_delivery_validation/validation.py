"""Structured validation results shared by every workflow layer."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from furniture_workflow.workflow_state import utc_now


class ValidationSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    severity: ValidationSeverity = ValidationSeverity.ERROR
    path: str = ""


@dataclass
class ValidationReport:
    stage: str
    issues: list[ValidationIssue] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)

    @property
    def passed(self) -> bool:
        return not any(issue.severity == ValidationSeverity.ERROR for issue in self.issues)

    def add_error(self, code: str, message: str, path: str = "") -> None:
        self.issues.append(ValidationIssue(code, message, ValidationSeverity.ERROR, path))

    def add_warning(self, code: str, message: str, path: str = "") -> None:
        self.issues.append(ValidationIssue(code, message, ValidationSeverity.WARNING, path))

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "passed": self.passed,
            "created_at": self.created_at,
            "issues": [
                {**asdict(issue), "severity": issue.severity.value} for issue in self.issues
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ValidationReport":
        return cls(
            stage=str(data["stage"]),
            created_at=str(data["created_at"]),
            issues=[
                ValidationIssue(
                    code=str(item["code"]),
                    message=str(item["message"]),
                    severity=ValidationSeverity(item["severity"]),
                    path=str(item.get("path", "")),
                )
                for item in data.get("issues", [])
            ],
        )
