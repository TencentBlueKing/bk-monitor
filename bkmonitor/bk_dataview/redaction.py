"""仪表盘配置展示共用的凭据脱敏规则。"""

import re
from typing import Any

REDACTED_VALUE = "[REDACTED]"
SENSITIVE_KEY_PATTERN = re.compile(
    r"password|passwd|passphrase|secret|credential|token|authorization|cookie|bearer"
    r"|api[_-]?key|access[_-]?key|private[_-]?key|app[_-]?key|basicAuthUser|username"
    r"|secureJsonData|httpHeaderValue\d+",
    re.IGNORECASE,
)
CREDENTIAL_TEXT_PATTERN = re.compile(
    r"://[^/\s@]+@"
    r"|\b(?:Bearer|Basic)\s+[A-Za-z0-9+/_=.-]+"
    r"|(?:password|passwd|passphrase|secret|token|credential|cookie|authorization|"
    r"api[_-]?key|access[_-]?key|private[_-]?key)[\"']?\s*[=:]\s*[\"']?[^\s,;\"'}\]\n]+",
    re.IGNORECASE,
)


def redact_config(value: Any, path: str, redacted_paths: list[str], *, credential_value: bool = False) -> Any:
    if isinstance(value, dict):
        named_secret = any(
            isinstance(value.get(field), str) and SENSITIVE_KEY_PATTERN.search(value[field])
            for field in ("name", "key")
        )
        result = {}
        for key, item in value.items():
            item_path = f"{path}/{key.replace('~', '~0').replace('/', '~1')}"
            if (SENSITIVE_KEY_PATTERN.search(key) or (key == "value" and named_secret)) and not isinstance(item, bool):
                result[key] = REDACTED_VALUE
                redacted_paths.append(item_path)
            else:
                result[key] = redact_config(
                    item,
                    item_path,
                    redacted_paths,
                    credential_value=credential_value or bool(named_secret and key in {"query", "current", "options"}),
                )
        return result
    if isinstance(value, list):
        return [
            redact_config(item, f"{path}/{index}", redacted_paths, credential_value=credential_value)
            for index, item in enumerate(value)
        ]
    if credential_value and value is not None and not isinstance(value, bool):
        redacted_paths.append(path)
        return REDACTED_VALUE
    if isinstance(value, str) and CREDENTIAL_TEXT_PATTERN.search(value):
        redacted_paths.append(path)
        return REDACTED_VALUE
    return value
