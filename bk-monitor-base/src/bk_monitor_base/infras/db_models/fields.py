import json
from typing import Any, cast, final

from bkcrypto.contrib.django.fields import SymmetricTextField
from django.db import models
from typing_extensions import override


@final
class TextJSONField(models.TextField):
    """基于TextField实现的自动序列化和反序列化的JsonField"""

    default_error_messages = {
        "invalid": "'%(value)s' is not a valid JsonFormat.",
    }
    description = "Stores data with json"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @override
    def to_python(self, value: Any) -> Any:
        """
        Converts the input value into the expected Python data type, raising
        django.core.exceptions.ValidationError if the data can't be converted.
        Returns the converted value. Subclasses should override this.
        """
        if isinstance(value, str):
            try:
                return json.loads(value)
            except ValueError as e:
                raise ValueError(f"Invalid JSON format: {value}") from e
        return value

    @override
    def get_db_prep_value(self, value: Any, connection: Any, prepared: bool = False) -> Any:
        return json.dumps(value)

    @override
    def from_db_value(self, value: Any, expression: Any, connection: Any) -> Any:  # pyright: ignore[reportUnusedParameter]
        return json.loads(value or "null")


class SymmetricJSONField(SymmetricTextField):
    """基于SymmetricTextField实现的对称加密JSONField"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @override
    def get_db_prep_value(self, value: Any, connection: Any, prepared: bool) -> Any:
        value = json.dumps(value)
        return super().get_db_prep_value(value, connection, prepared)

    @override
    def from_db_value(self, value: Any, expression: Any, connection: Any, context: Any = None) -> Any:
        new_value: str | None = cast(str | None, super().from_db_value(value, expression, connection, context))
        return json.loads(new_value or "null")
