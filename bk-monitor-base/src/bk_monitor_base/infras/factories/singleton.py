from typing import Any


class Singleton:
    _instance: Any = None

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:
        if not isinstance(cls._instance, cls):
            cls._instance = object.__new__(cls, *args, **kwargs)
        return cls._instance
