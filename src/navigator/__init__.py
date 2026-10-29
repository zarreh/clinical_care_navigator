"""Clinical Care Navigator: a patient-facing clinical assistant that is allowed to refuse."""

from __future__ import annotations

import warnings


def install_warning_filters() -> None:
    """Silence one known-harmless upstream warning, and only that one.

    `langchain-openai` calls `model_dump()` on the OpenAI SDK's streaming chunks, and
    the SDK's `parsed` field (used for structured output) is typed `None` in the base
    chunk model, so Pydantic warns on *every* structured-output call:

        PydanticSerializationUnexpectedValue(Expected `none` ... field_name='parsed' ...)

    It is noise from the interplay of those two libraries and says nothing about this
    code. The filter requires `field_name='parsed'` so a genuine serializer warning for
    any other field still shows.
    """
    warnings.filterwarnings(
        "ignore",
        message=r"(?s)Pydantic serializer warnings:.*field_name='parsed'",
        category=UserWarning,
        module=r"pydantic\.main",
    )


install_warning_filters()
