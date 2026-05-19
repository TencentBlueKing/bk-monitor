"""
轻量级 Grok 实现，仅使用标准库 re 模块。
替代第三方 pygrok 库，所有内置模式已改写为 RE2/标准 re 兼容语法。
"""

import re
from typing import Any

from apps.log_databus.handlers.grok.patterns import ALL_PATTERNS

# 内置模式字典，模块加载时一次性构建
BUILTIN_PATTERNS: dict[str, str] = {p["name"]: p["pattern"] for p in ALL_PATTERNS}


class Grok:
    def __init__(self, pattern: str, custom_patterns: dict[str, str] | None = None):
        """
        初始化 Grok 实例。

        :param pattern: Grok 模式字符串
        :param custom_patterns: 自定义模式字典 {name: regex_str}，会覆盖同名内置模式
        """
        self.pattern = pattern
        self._type_mapper: dict[str, str] = {}

        # 合并内置模式和自定义模式（自定义优先）
        self._available_patterns: dict[str, str] = dict(BUILTIN_PATTERNS)
        if custom_patterns:
            self._available_patterns.update(custom_patterns)

        # 编译
        self.regex_obj: re.Pattern = self._compile()

    def _compile(self) -> re.Pattern:
        """
        将 Grok 模式展开为标准正则表达式并编译。
        """
        self._type_mapper = {}
        expanded = self.pattern

        while True:
            # 提取类型映射：%{PATTERN:field:type}
            type_matches = re.findall(r"%{(\w+):(\w+):(\w+)}", expanded)
            for _, field_name, field_type in type_matches:
                self._type_mapper[field_name] = field_type

            # 替换 %{PATTERN:field} 或 %{PATTERN:field:type} 为命名捕获组
            expanded = re.sub(
                r"%{(\w+):(\w+)(?::\w+)?}",
                lambda m: f"(?P<{m.group(2)}>{self._available_patterns[m.group(1)]})",
                expanded,
            )

            # 替换 %{PATTERN} 为非捕获组
            expanded = re.sub(
                r"%{(\w+)}",
                lambda m: f"({self._available_patterns[m.group(1)]})",
                expanded,
            )

            # 没有更多 grok 引用时退出
            if re.search(r"%{\w+(:\w+)?}", expanded) is None:
                break

        return re.compile(expanded)

    def match(self, text: str) -> dict[str, Any] | None:
        """
        在 text 中搜索匹配（非全文匹配，等同于 re.search）。
        匹配成功返回 {field: value} 字典，失败返回 None。
        类型映射会自动将 int/float 字段转换。
        """
        match_obj = self.regex_obj.search(text)
        if match_obj is None:
            return None

        matches = match_obj.groupdict()

        # 类型转换
        for key, value in matches.items():
            if key in self._type_mapper and value is not None:
                try:
                    if self._type_mapper[key] == "int":
                        matches[key] = int(value)
                    elif self._type_mapper[key] == "float":
                        matches[key] = float(value)
                except (ValueError, TypeError):
                    pass

        return matches
