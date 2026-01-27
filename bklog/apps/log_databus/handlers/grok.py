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
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from pygrok import Grok

from apps.exceptions import ValidationError
from apps.log_databus.constants import GrokOriginEnum
from apps.log_databus.exceptions import GrokCircularReferenceException
from apps.log_databus.models import GrokInfo


class GrokHandler:
    def __init__(self, bk_biz_id: int):
        self.bk_biz_id = bk_biz_id

    @staticmethod
    def list_grok_info(params: dict) -> dict:
        """
        获取 Grok 模式列表
        """
        q = Q(origin=GrokOriginEnum.BUILTIN.value) | Q(bk_biz_id=params["bk_biz_id"])
        if params.get("origin"):
            q &= Q(origin=params["origin"])
        if params.get("updated_by"):
            q &= Q(updated_by=params["updated_by"])
        if params.get("keyword"):
            q &= (
                Q(name__icontains=params["keyword"])
                | Q(pattern__icontains=params["keyword"])
                | Q(description__icontains=params["keyword"])
            )

        ordering = ["-origin", params.get("ordering") or "-updated_at"]

        grok_list = GrokInfo.objects.filter(q).order_by(*ordering).values()
        total = grok_list.count()
        if params.get("page") and params.get("pagesize"):
            grok_list = list(Paginator(grok_list, params["pagesize"]).page(params["page"]))

        return {"total": total, "list": grok_list}

    @classmethod
    def create_grok_info(cls, params: dict) -> dict:
        """
        创建 Grok 模式
        """
        cls.validate_references(params["bk_biz_id"], params["pattern"])
        custom_patterns = cls.get_custom_grok_patterns(params["bk_biz_id"])
        custom_patterns[params["name"]] = params["pattern"]
        is_circular, circular_path = cls.detect_circular_reference(params["name"], custom_patterns)
        if is_circular:
            raise GrokCircularReferenceException(
                GrokCircularReferenceException.MESSAGE.format(path="->".join(circular_path))
            )

        grok = GrokInfo.objects.create(
            bk_biz_id=params["bk_biz_id"],
            name=params["name"],
            pattern=params["pattern"],
            sample=params.get("sample"),
            description=params.get("description"),
        )
        return {"id": grok.id}

    @classmethod
    def update_grok_info(cls, params: dict):
        """
        更新 Grok 模式
        """
        cls.validate_references(2, params["pattern"])
        custom_patterns = cls.get_custom_grok_patterns(2)
        custom_patterns[params["name"]] = params["pattern"]
        has_circle, path = cls.detect_circular_reference(params["name"], custom_patterns)
        if has_circle:
            raise ValidationError(_("Grok 模式 {} 存在循环引用").format("->".join(path)))

        grok_info = GrokInfo.objects.filter(id=params["id"]).first()
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
        if not grok_info or grok_info.origin != GrokOriginEnum.CUSTOM.value:
            return

        # 检查是否有其他模式引用了该模式
        custom_patterns = GrokInfo.objects.filter(bk_biz_id=grok_info.bk_biz_id)
        for pattern in custom_patterns:
            reference_patterns = cls._extract_pattern_references(pattern.pattern)
            if grok_info.name in reference_patterns:
                return

        grok_info.delete()

    @classmethod
    def debug(cls, params) -> dict:
        """
        调试 Grok 模式
        """
        custom_grok_patterns = GrokInfo.objects.filter(bk_biz_id=params["bk_biz_id"]).values()
        custom_grok_map = {grok["name"]: grok["pattern"] for grok in custom_grok_patterns}
        grok = Grok(params["pattern"], custom_patterns=custom_grok_map)
        return grok.match(params["sample"])

    @staticmethod
    def is_grok_pattern(pattern: str) -> bool:
        """
        判断是否为 Grok 模式
        """
        return True if re.search("%{\w+(:\w+)?}", pattern) else False

    @classmethod
    def get_custom_grok_patterns(cls, bk_biz_id: int) -> dict:
        """
        获取自定义 Grok 模式
        """
        custom_grok_patterns = GrokInfo.objects.filter(bk_biz_id=bk_biz_id).values("name", "pattern")
        custom_grok_map = {grok["name"]: grok["pattern"] for grok in custom_grok_patterns}
        return custom_grok_map

    @staticmethod
    def _extract_pattern_references(pattern: str) -> set[str]:
        """
        从 Grok 模式中提取引用的其他模式名称(不包含嵌套模式)
        """
        references = re.findall(r"%{(\w+)(?::\w+)?(?::\w+)?}", pattern)
        return set(references)

    @classmethod
    def validate_references(cls, bk_biz_id: int, pattern: str) -> None:
        """
        验证 Grok 模式中引用的其他模式是否存在
        """
        grok_patterns = GrokInfo.objects.filter(
            Q(bk_biz_id=bk_biz_id) | Q(origin=GrokOriginEnum.BUILTIN.value)
        ).values()
        grok_patterns = [grok["name"] for grok in grok_patterns]
        references = cls._extract_pattern_references(pattern)
        for reference in references:
            if reference not in grok_patterns:
                raise ValidationError(_("Grok 模式 {} 不存在").format(reference))

    @staticmethod
    def expand_custom_patterns_to_regex(params: dict) -> str:
        """
        将自定义模式替换为正则表达式，内置模式保持原样
        """
        bk_biz_id = params["bk_biz_id"]
        result = params["pattern"]

        # 获取当前业务下的所有自定义模式（origin=custom）
        custom_grok_patterns = GrokInfo.objects.filter(bk_biz_id=bk_biz_id, origin=GrokOriginEnum.CUSTOM.value).values(
            "name", "pattern"
        )
        custom_patterns_map = {grok["name"]: grok["pattern"] for grok in custom_grok_patterns}

        # 参考 pygrok 的方式，循环展开直到没有自定义模式可以替换
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

    @classmethod
    def validate_circular_reference(cls, pattern_name, patterns_map) -> None:
        is_circular, circular_path = cls.detect_circular_reference(pattern_name, patterns_map)
        if is_circular:
            raise GrokCircularReferenceException(
                GrokCircularReferenceException.MESSAGE.format(path="->".join(circular_path))
            )
