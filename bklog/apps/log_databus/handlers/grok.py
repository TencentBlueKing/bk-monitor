"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

import re

from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Q
from pygrok import Grok

from apps.log_databus.exceptions import (
    GrokCircularReferenceException,
    GrokReferencedException,
    GrokPatternNotFoundException,
    DuplicateGrokPatternException,
)
from apps.log_databus.models import GrokInfo


class GrokHandler:
    def __init__(self, bk_biz_id: int):
        self.bk_biz_id = bk_biz_id

    @staticmethod
    def is_grok_pattern(pattern: str) -> bool:
        """
        判断是否为 Grok 模式
        """
        return True if re.search("%{\w+(:\w+)?}", pattern) else False

    def get_custom_patterns_map(self) -> dict:
        """
        获取自定义 Grok 模式
        """
        custom_patterns = GrokInfo.objects.filter(bk_biz_id=self.bk_biz_id).values("name", "pattern")
        return {grok["name"]: grok["pattern"] for grok in custom_patterns}

    def get_all_pattern_names(self) -> list:
        """
        获取所有 Grok 模式名称
        """
        all_patterns = GrokInfo.objects.filter(Q(bk_biz_id=self.bk_biz_id) | Q(is_builtin=True)).values_list(
            "name", flat=True
        )
        return list(all_patterns)

    @staticmethod
    def _extract_pattern_references(pattern: str) -> set[str]:
        """
        从 Grok 模式中提取引用的其他模式名称(不包含嵌套模式)
        """
        references = re.findall(r"%{(\w+)(?::\w+)?(?::\w+)?}", pattern)
        return set(references)

    def validate_references_exist(self, pattern: str) -> None:
        """
        验证 Grok 模式中引用的其他模式是否存在
        """
        all_pattern_names = set(self.get_all_pattern_names())
        references = self._extract_pattern_references(pattern)
        for reference in references:
            if reference not in all_pattern_names:
                raise GrokPatternNotFoundException(GrokPatternNotFoundException.MESSAGE.format(pattern_name=reference))

    @classmethod
    def detect_circular_reference(
        cls,
        pattern_name: str,
        patterns_map: dict[str, str],
        path: list[str] | None = None,
        visiting: set[str] | None = None,
    ) -> tuple[bool, list[str]]:
        """DFS 检测循环引用"""
        if path is None:
            path = []
        if visiting is None:
            visiting = set()

        # 检测到循环
        if pattern_name in visiting:
            cycle_start = path.index(pattern_name)
            return True, path[cycle_start:] + [pattern_name]

        # 模式不存在/内置模式
        if pattern_name not in patterns_map:
            return False, []

        # 标记为正在访问
        visiting.add(pattern_name)
        path.append(pattern_name)

        # 递归检查所有引用的子模式
        for ref in cls._extract_pattern_references(patterns_map[pattern_name]):
            has_cycle, cycle_path = cls.detect_circular_reference(ref, patterns_map, path, visiting)
            if has_cycle:
                return True, cycle_path

        # 回溯
        path.pop()
        visiting.remove(pattern_name)

        return False, []

    def validate_circular_reference(self, pattern_name, pattern):
        """
        验证 Grok 模式中是否存在循环引用
        """
        custom_patterns = self.get_custom_patterns_map()
        custom_patterns[pattern_name] = pattern
        is_circular, circular_path = self.detect_circular_reference(pattern_name, custom_patterns)
        if is_circular:
            raise GrokCircularReferenceException(
                GrokCircularReferenceException.MESSAGE.format(path="->".join(circular_path))
            )

    @staticmethod
    def list_grok_info(params: dict) -> dict:
        """
        获取 Grok 模式列表
        """
        q = Q(is_builtin=True) | Q(bk_biz_id=params["bk_biz_id"])
        if params.get("is_builtin") is not None:
            q &= Q(is_builtin=params["is_builtin"])
        if params.get("updated_by"):
            q &= Q(updated_by=params["updated_by"])
        if params.get("keyword"):
            q &= (
                Q(name__icontains=params["keyword"])
                | Q(pattern__icontains=params["keyword"])
                | Q(description__icontains=params["keyword"])
                | Q(updated_by__icontains=params["keyword"])
            )
        if params.get("ordering"):
            ordering = [params["ordering"]]
        else:
            ordering = ["is_builtin", "-updated_at"]

        grok_list = GrokInfo.objects.filter(q).order_by(*ordering).values()
        total = grok_list.count()
        if params.get("page") and params.get("pagesize"):
            grok_list = list(Paginator(grok_list, params["pagesize"]).page(params["page"]))

        return {"total": total, "list": grok_list}

    def create_grok_info(self, params: dict) -> dict:
        """
        创建 Grok 模式
        """
        self.validate_references_exist(params["pattern"])
        self.validate_circular_reference(params["name"], params["pattern"])
        try:
            grok = GrokInfo.objects.create(
                bk_biz_id=self.bk_biz_id,
                name=params["name"],
                pattern=params["pattern"],
                sample=params.get("sample"),
                description=params.get("description"),
            )
        except IntegrityError:
            raise DuplicateGrokPatternException

        return {"id": grok.id}

    def update_grok_info(self, params: dict):
        """
        更新 Grok 模式
        """
        self.validate_references_exist(params["pattern"])
        grok_info = GrokInfo.objects.filter(id=params["id"]).first()
        self.validate_circular_reference(grok_info.name, params["pattern"])

        update_fields = ["pattern", "sample", "description"]
        for field in update_fields:
            setattr(grok_info, field, params[field])

        grok_info.save(update_fields=update_fields)

    @classmethod
    def delete_grok_info(cls, grok_info_id: int):
        """
        删除 Grok 模式
        """
        grok_info = GrokInfo.objects.filter(id=grok_info_id).first()
        if not grok_info or grok_info.is_builtin:
            return

        # 检查是否有其他模式引用了该模式
        custom_grok_patterns = GrokInfo.objects.filter(bk_biz_id=grok_info.bk_biz_id).all()
        referenced_by = []
        for grok in custom_grok_patterns:
            reference_patterns = cls._extract_pattern_references(grok.pattern)
            if grok_info.name in reference_patterns:
                referenced_by.append(grok.name)
        if referenced_by:
            raise GrokReferencedException(
                GrokReferencedException.MESSAGE.format(referenced_by=", ".join(referenced_by))
            )

        grok_info.delete()

    @staticmethod
    def get_updated_by_list(bk_biz_id) -> list:
        """
        获取更新人列表
        """
        updated_by_list = (
            GrokInfo.objects.filter(Q(bk_biz_id=bk_biz_id) | Q(is_builtin=True))
            .values_list("updated_by", flat=True)
            .distinct()
        )
        return list(updated_by_list)

    def debug(self, params) -> dict:
        """
        调试 Grok 模式
        """
        self.validate_references_exist(params["pattern"])
        custom_patterns_map = self.get_custom_patterns_map()

        # 将用户输入的模式注册为自定义模式（_matched 字段的值为表达式匹配到的原文片段）
        wrapper_pattern_name = "_GROK_DEBUG_WRAPPER"
        fallback_field = "_matched"
        custom_patterns_map[wrapper_pattern_name] = params["pattern"]
        grok = Grok(f"%{{{wrapper_pattern_name}:{fallback_field}}}", custom_patterns=custom_patterns_map)

        result = grok.match(params["sample"])
        return result

    def replace_custom_patterns(self, pattern: str) -> str:
        """
        将自定义模式替换为正则表达式，内置模式保持原样
        """
        self.validate_references_exist(pattern)

        result = pattern
        custom_patterns_map = self.get_custom_patterns_map()
        while True:
            prev_result = result
            # 替换 %{PATTERN_NAME:field_name} 或 %{PATTERN_NAME:field_name:type} 格式
            result = re.sub(
                r"%{(\w+):(\w+)(?::\w+)?}",
                lambda m: f"(?P<{m.group(2)}>{custom_patterns_map[m.group(1)]})"
                if m.group(1) in custom_patterns_map
                else m.group(0),
                result,
            )
            # 替换 %{PATTERN_NAME} 格式
            result = re.sub(
                r"%{(\w+)}",
                lambda m: f"({custom_patterns_map[m.group(1)]})" if m.group(1) in custom_patterns_map else m.group(0),
                result,
            )
            # 如果没有变化，说明已完成展开（剩下的都是内置模式）
            if result == prev_result:
                break

        return result
