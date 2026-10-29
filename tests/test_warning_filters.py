"""The one upstream warning we silence, and nothing else."""

from __future__ import annotations

import warnings

from navigator import install_warning_filters

_PARSED = (
    "Pydantic serializer warnings:\n  PydanticSerializationUnexpectedValue(Expected `none` - "
    "serialized value may not be as expected [field_name='parsed', input_value=IntentAssessment()])"
)


def _emit(message: str) -> list[warnings.WarningMessage]:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")  # what a test run does; our filter is re-applied below
        install_warning_filters()
        warnings.warn_explicit(
            message, UserWarning, filename="pydantic/main.py", lineno=475, module="pydantic.main"
        )
    return caught


def test_the_known_parsed_field_warning_is_silenced() -> None:
    assert _emit(_PARSED) == []


def test_a_serializer_warning_about_any_other_field_still_shows() -> None:
    other = _PARSED.replace("field_name='parsed'", "field_name='claims'")
    assert len(_emit(other)) == 1
