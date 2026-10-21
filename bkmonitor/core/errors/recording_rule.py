"""RecordingRule 公共预解析的业务错误。"""

from core.errors.common import DrfApiError


class RecordingRulePreviewError(DrfApiError):
    status_code = 400
    name = "RecordingRule 预解析失败"

    def __init__(self, error_code: str, message: str, path: str):
        super().__init__(
            context={"message": f"{path}: {message}"},
            data={"errors": [{"code": error_code, "message": message, "path": path}]},
        )
