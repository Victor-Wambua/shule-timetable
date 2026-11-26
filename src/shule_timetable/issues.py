"""Problems found in the input, reported with a pointer to where they are."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Issue:
    severity: str  # "error" | "warning"
    code: str  # stable machine-readable id, e.g. "teacher-overloaded"
    message: str
    where: str = ""  # e.g. "teachers.csv:7"

    def __str__(self) -> str:
        tag = "ERROR" if self.severity == "error" else "warning"
        loc = f" {self.where}:" if self.where else ""
        return f"{tag}{loc} {self.message}"


class InputError(Exception):
    """Raised when the input cannot be turned into a School."""

    def __init__(self, issues: list[Issue]) -> None:
        self.issues = issues
        errors = [i for i in issues if i.severity == "error"]
        super().__init__("\n".join(str(i) for i in errors) or "invalid input")


def errors_of(issues: list[Issue]) -> list[Issue]:
    return [i for i in issues if i.severity == "error"]
