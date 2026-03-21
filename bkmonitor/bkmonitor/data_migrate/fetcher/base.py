from typing import Any

from django.db.models import Model

# 导出结果类型, 包含模型类、过滤条件、排除条件
FetcherResultType = tuple[type[Model], dict[str, Any] | None, dict[str, Any] | None]
