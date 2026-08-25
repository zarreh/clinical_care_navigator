"""Trace-boundary PHI redaction (docs/PLAN.md §5.7).

Redaction runs at the **observability boundary** — the structured-log processor
chain and anything handed to a third-party tracer — so a developer cannot leak a
patient identifier into a log line or a LangSmith span by forgetting to scrub it
at the call site. It is centralised here and installed once, not sprinkled.

Two honesty rules the docs state plainly (§5.7):

- The data is Synthea and therefore **not PHI**. This is an architectural
  demonstration of a control, not a control operating on real patient data;
  claiming otherwise would be exactly the overclaim §3.7 exists to prevent.
- The test is **falsifiable**: for the store's own patients, no name, birth date
  or identifier appears in any emitted log line — asserted against the store's
  values, not against a regex guess.

The patient's *own* answer is deliberately **not** redacted: a person is allowed
to read their own record. Redaction protects the trace/log path, not the API
response the patient receives.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from navigator.store.models import Patient

# Identifiers shorter than this are not treated as secrets: a two-character token
# would redact far more than it protects. Synthea names carry numeric suffixes
# (e.g. "Sanford861"), so real identifiers comfortably clear this floor.
_MIN_SECRET_LENGTH = 3

_PLACEHOLDER = "[redacted]"


class PhiRedactor:
    """Redacts a fixed set of patient identifiers from arbitrary text and nested
    structures. Case-insensitive and substring-based on purpose: over-redacting
    a log line is the safe direction, and it makes the falsifiable test exact —
    no identifier can survive in any form."""

    def __init__(self, secrets: Iterable[str], placeholder: str = _PLACEHOLDER) -> None:
        cleaned = {s.strip() for s in secrets if s and len(s.strip()) >= _MIN_SECRET_LENGTH}
        # Longest-first so a family name is redacted before a shorter substring
        # of it could match and leave a fragment behind.
        self._secrets: tuple[str, ...] = tuple(sorted(cleaned, key=len, reverse=True))
        self._placeholder = placeholder
        self._pattern: re.Pattern[str] | None = (
            re.compile("|".join(re.escape(s) for s in self._secrets), re.IGNORECASE)
            if self._secrets
            else None
        )

    @property
    def secrets(self) -> tuple[str, ...]:
        return self._secrets

    def redact(self, text: str) -> str:
        if self._pattern is None:
            return text
        return self._pattern.sub(self._placeholder, text)

    def scrub(self, value: Any) -> Any:
        """Recursively redact every string inside a dict/list/tuple payload,
        leaving non-string leaves untouched."""
        if isinstance(value, str):
            return self.redact(value)
        if isinstance(value, dict):
            return {key: self.scrub(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self.scrub(item) for item in value]
        return value

    @classmethod
    def from_patients(cls, patients: Iterable[Patient]) -> PhiRedactor:
        secrets: list[str] = []
        for patient in patients:
            secrets.extend(
                (patient.given_name, patient.family_name, patient.birth_date, patient.patient_id)
            )
        return cls(secrets)


def redacting_processor(redactor: PhiRedactor) -> Any:
    """A structlog processor that scrubs every value in the event dict before it
    is rendered — the enforced boundary for logs. Placed just before the
    renderer so it sees the fully-assembled event."""

    def processor(_logger: object, _method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
        return {key: redactor.scrub(value) for key, value in event_dict.items()}

    return processor
