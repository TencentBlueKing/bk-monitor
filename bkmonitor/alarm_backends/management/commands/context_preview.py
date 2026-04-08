"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from django.core.management.base import BaseCommand

from alarm_backends.core.context import ActionContext
from bkmonitor.documents import ActionInstanceDocument, AlertDocument
from bkmonitor.models import ActionInstance

logger = logging.getLogger("fta_action.run")


class Command(BaseCommand):
    """告警上下文变量预览命令.

    预览告警通知模板中可用的上下文变量及其结构。

    一致性保证
    ------------
    本命令使用的上下文数据与实际通知渲染时完全一致：

    - 使用相同的 ActionContext 对象
    - 调用相同的 context.get_dictionary() 方法
    - 遵循 Jinja2 的变量访问逻辑

    实际通知流程：

    1. Sender 类接收 ActionContext 对象
    2. 调用 context.get_dictionary() 获取上下文字典
    3. 使用 Jinja2Renderer.render() 渲染模板

    本命令流程：

    1. 创建相同的 ActionContext 对象
    2. 调用相同的 context.get_dictionary() 方法
    3. 提供与 Jinja2 一致的变量访问

    因此，预览结果与实际通知内容完全一致

    使用方法
    --------
    ::

        python manage.py context_preview <alert_id> [--action-id <action_id>] [--variable <var_path>]

    参数说明
    --------
    :param alert_id: 告警 ID（必需）
    :param action-id: 动作实例 ID（可选，如果不指定则使用第一个通知动作）
    :param variable: 指定要查询的模板变量（可选）

        支持格式（与 Jinja2 模板完全一致）：

        1. 点号访问：``target.business.bk_biz_name``
        2. 模板格式：``{{ target.business.bk_biz_name }}``
        3. 数字索引：``list[0]`` 或 ``list.0``
        4. 字符串键：``dict['key']`` 或 ``dict["key"]`` 或 ``dict.key``
        5. 混合使用：``item.query_configs[0]['metric_id']``

        .. warning::
           Shell 转义注意事项：

           - 务必用双引号包裹整个参数：``--variable "path.to[0]['key']"``
           - 或使用更简单的点号语法：``--variable "path.to[0].key"``

    :param depth: 递归深度（可选，默认为2，最大为3）
    :param format: 输出格式（可选，template=模板风格[默认]，tree=树形结构，json=JSON格式）

    示例
    ----
    1. 预览所有可用的模板变量（默认模板风格）::

        python manage.py context_preview 12345

    输出示例::

        可用的模板变量：
        {{ target.business.bk_biz_name        }} -> '蓝鲸'
        {{ target.business.bk_alarm_rvc_man   }} -> ['admin', 'operator']
        {{ alert.alert_name                   }} -> '磁盘空间不足'
        {{ alert.dimensions                   }} -> {'ip': '10.0.0.1', 'bk_cloud_id': '0'}
        总计 156 个可用变量

    2. 查询指定模板变量的值::

        python manage.py context_preview 12345 --variable "target.business.bk_alarm_rvc_man"
        # 或直接复制模板格式（带花括号）
        python manage.py context_preview 12345 --variable "{{ target.business.bk_alarm_rvc_man }}"

    3. 支持各种访问方式（与 Jinja2 模板完全一致）::

        python manage.py context_preview 12345 --variable "strategy.item.query_configs[0]"
        python manage.py context_preview 12345 --variable "strategy.item.query_configs.0"  # 等价于 [0]
        python manage.py context_preview 12345 --variable "alert.dimensions[0].key"
    """

    def add_arguments(self, parser):
        parser.add_argument("alert_id", type=int, help="告警 ID")
        parser.add_argument("--action-id", type=int, help="动作实例 ID（可选）")
        parser.add_argument(
            "--variable",
            type=str,
            help="指定要查询的模板变量，支持完整 Jinja2 格式：'var.path'、'list[0]'、'dict[\"key\"]'",
        )
        parser.add_argument("--depth", type=int, default=2, help="递归深度（默认2，最大3）")
        parser.add_argument(
            "--format", type=str, default="template", choices=["template", "tree", "json"], help="输出格式"
        )

    def handle(self, alert_id, *args, **options):
        action_id = options.get("action_id")
        variable = options.get("variable")
        depth = min(options.get("depth", 2), 3)  # 最大深度3
        output_format = options.get("format", "template")  # 默认模板格式

        try:
            # 1. 获取动作实例
            action_instance = self._get_action_instance(alert_id, action_id)
            if not action_instance:
                self.stdout.write(self.style.ERROR(f"告警 ID {alert_id} 没有关联的通知动作"))
                return

            # 2. 获取告警文档
            alert_docs = self._get_alert_documents(action_instance, alert_id)
            if not alert_docs:
                self.stdout.write(self.style.ERROR("无法获取告警文档"))
                return

            # 3. 创建 ActionContext
            context = ActionContext(
                action=action_instance,
                alerts=alert_docs,
                use_alert_snap=False,
            )
            context_dict = context.get_dictionary()

            # 4. 如果指定了变量，只查询该变量
            if variable:
                self._output_single_variable(context_dict, variable, alert_id, action_instance)
                return

            # 5. 否则输出所有变量
            self._output_header(alert_id, action_instance, len(alert_docs))

            if output_format == "json":
                self._output_json_format(context_dict, depth)
            elif output_format == "tree":
                self._output_tree_format(context_dict, depth)
            else:  # template
                self._output_template_format(context_dict, depth)

        except Exception as e:
            logger.exception(f"preview context failed: alert_id={alert_id}, error={str(e)}")
            self.stdout.write(self.style.ERROR(f"预览失败: {str(e)}"))

    def _get_action_instance(self, alert_id, action_id=None):
        """获取动作实例.

        优先使用指定的 action_id，如果未指定则从 ES 中查找第一个通知类型的动作实例。
        这样做是为了确保预览的上下文与实际发送通知时使用的上下文一致。

        :param alert_id: 告警 ID
        :param action_id: 动作实例 ID（可选）
        :return: ActionInstance 对象或 None
        """
        if action_id:
            try:
                action_instance = ActionInstance.objects.get(id=action_id)
                if action_instance.action_plugin.get("plugin_type") != "notice":
                    self.stdout.write(self.style.WARNING(f"动作实例 {action_id} 不是通知类型的动作"))
                    return None
                return action_instance
            except ActionInstance.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"动作实例 {action_id} 不存在"))
                return None

        # 从 ES 查找第一个通知动作
        action_docs = ActionInstanceDocument.mget_by_alert(
            alert_ids=[alert_id],
            include={"action_plugin_type": "notice"},
            ordering=["-create_time"],
        )

        if not action_docs:
            return None

        try:
            return ActionInstance.objects.get(id=action_docs[0].raw_id)
        except ActionInstance.DoesNotExist:
            return None

    def _get_alert_documents(self, action_instance, fallback_alert_id):
        """获取告警文档列表.

        从 action_instance.alerts 中提取告警 ID，如果为空则使用 fallback_alert_id。
        这样做是为了支持多告警场景，确保上下文包含所有相关告警的信息。

        :param action_instance: 动作实例对象
        :param fallback_alert_id: 备用告警 ID
        :return: AlertDocument 列表
        """
        alert_ids = []

        if action_instance.alerts:
            try:
                if isinstance(action_instance.alerts, list):
                    for aid in action_instance.alerts:
                        try:
                            alert_ids.append(int(aid) if isinstance(aid, str) else aid)
                        except (ValueError, TypeError):
                            pass
                else:
                    try:
                        alert_ids = [
                            int(action_instance.alerts)
                            if isinstance(action_instance.alerts, str)
                            else action_instance.alerts
                        ]
                    except (ValueError, TypeError):
                        pass
            except Exception:
                pass

        if not alert_ids:
            alert_ids = [fallback_alert_id]

        alert_docs = []
        for alert_id in alert_ids:
            try:
                alert_doc = AlertDocument.get(id=alert_id)
                if alert_doc:
                    alert_docs.append(alert_doc)
            except Exception:
                pass

        return alert_docs

    def _output_header(self, alert_id, action_instance, alert_count):
        """输出头部信息"""
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 80))
        self.stdout.write(self.style.SUCCESS("告警上下文变量预览"))
        self.stdout.write(self.style.SUCCESS("=" * 80 + "\n"))

        self.stdout.write(f"告警 ID: {alert_id}")
        self.stdout.write(f"动作实例 ID: {action_instance.id}")
        self.stdout.write(f"关联告警数: {alert_count}")
        self.stdout.write("\n" + "-" * 80 + "\n")

    def _output_tree_format(self, context_dict, max_depth):
        """树形格式输出"""

        def get_object_info(obj, depth=0, prefix="", var_name=""):
            """递归获取对象信息"""
            if depth >= max_depth:
                return []

            lines = []
            indent = "  " * depth

            # 基本类型
            if isinstance(obj, str | int | float | bool | type(None)):
                value_str = repr(obj)[:100]
                lines.append(f"{indent}└─ {var_name}: {type(obj).__name__} = {value_str}")
                return lines

            # 字典类型
            if isinstance(obj, dict):
                items = list(obj.items())[:15]  # 最多15个
                for i, (key, value) in enumerate(items):
                    is_last = i == len(items) - 1
                    connector = "└─" if is_last else "├─"
                    value_type = type(value).__name__

                    if isinstance(value, str | int | float | bool | type(None)):
                        value_str = repr(value)[:60]
                        lines.append(f"{indent}{connector} {key}: {value_type} = {value_str}")
                    else:
                        lines.append(f"{indent}{connector} {key}: {value_type}")
                        sub_indent = "  " if is_last else "│ "
                        lines.extend(get_object_info(value, depth + 1, prefix + sub_indent, key))

                if len(obj) > 15:
                    lines.append(f"{indent}└─ ... ({len(obj) - 15} more items)")
                return lines

            # 列表类型
            if isinstance(obj, list | tuple):
                if len(obj) == 0:
                    lines.append(f"{indent}└─ (empty list)")
                    return lines

                first_item = obj[0]
                is_simple = isinstance(first_item, str | int | float | bool | type(None))

                if is_simple:
                    # 简单类型列表，显示前5个值
                    for i, item in enumerate(obj[:5]):
                        lines.append(f"{indent}└─ [{i}]: {type(item).__name__} = {repr(item)[:60]}")
                    if len(obj) > 5:
                        lines.append(f"{indent}└─ ... ({len(obj) - 5} more items, total: {len(obj)})")
                else:
                    # 复杂类型列表，显示第一个元素的结构
                    lines.append(f"{indent}└─ [0]: {type(first_item).__name__}")
                    lines.extend(get_object_info(first_item, depth + 1, prefix, "[0]"))
                    if len(obj) > 1:
                        lines.append(f"{indent}└─ ... ({len(obj) - 1} more items, total: {len(obj)})")
                return lines

            # 对象类型
            try:
                attrs = [attr for attr in dir(obj) if not attr.startswith("_")]
                properties = []
                for attr in attrs[:20]:
                    try:
                        value = getattr(obj, attr)
                        if not callable(value):
                            properties.append((attr, value))
                    except Exception:
                        pass

                for i, (attr, value) in enumerate(properties[:15]):
                    is_last = (i == len(properties) - 1) or (i == 14)
                    connector = "└─" if is_last else "├─"
                    value_type = type(value).__name__

                    if isinstance(value, str | int | float | bool | type(None)):
                        value_str = repr(value)[:60]
                        lines.append(f"{indent}{connector} {attr}: {value_type} = {value_str}")
                    else:
                        lines.append(f"{indent}{connector} {attr}: {value_type}")
                        if depth < max_depth - 1:
                            sub_indent = "  " if is_last else "│ "
                            lines.extend(get_object_info(value, depth + 1, prefix + sub_indent, attr))

                if len(properties) > 15:
                    lines.append(f"{indent}└─ ... ({len(properties) - 15} more attributes)")
            except Exception:
                pass

            return lines

        # 输出所有顶层变量
        for key in sorted(context_dict.keys()):
            value = context_dict[key]
            value_type = type(value).__name__

            self.stdout.write(self.style.SUCCESS(f"\n{{{{ {key} }}}}: {value_type}"))
            info_lines = get_object_info(value, depth=0, prefix="", var_name=key)
            for line in info_lines[:30]:
                self.stdout.write(line)
            if len(info_lines) > 30:
                self.stdout.write(f"  ... ({len(info_lines) - 30} more lines)")

        self.stdout.write("\n" + "=" * 80 + "\n")

    def _output_json_format(self, context_dict, max_depth):
        """JSON格式输出"""
        import json

        def serialize_object(obj, depth=0):
            """序列化对象为JSON可序列化的格式"""
            if depth >= max_depth:
                return f"<{type(obj).__name__}>"

            if isinstance(obj, str | int | float | bool | type(None)):
                return obj

            if isinstance(obj, dict):
                return {k: serialize_object(v, depth + 1) for k, v in list(obj.items())[:20]}

            if isinstance(obj, list | tuple):
                if len(obj) == 0:
                    return []

                # 对于简单类型列表，直接返回值；对于复杂类型，递归处理前5个
                if isinstance(obj[0], str | int | float | bool | type(None)):
                    # 简单类型，返回前10个值
                    result = obj[:10]
                    if len(obj) > 10:
                        result = list(result) + [f"... ({len(obj) - 10} more items, total: {len(obj)})"]
                    return result
                else:
                    # 复杂类型，序列化前5个
                    result = [serialize_object(item, depth + 1) for item in obj[:5]]
                    if len(obj) > 5:
                        result.append(f"... ({len(obj) - 5} more items, total: {len(obj)})")
                    return result

            # 对象类型
            try:
                result = {"_type": type(obj).__name__}
                attrs = [attr for attr in dir(obj) if not attr.startswith("_")]
                for attr in attrs[:15]:
                    try:
                        value = getattr(obj, attr)
                        if not callable(value):
                            result[attr] = serialize_object(value, depth + 1)
                    except Exception:
                        pass
                return result
            except Exception:
                return f"<{type(obj).__name__}>"

        serialized = {}
        for key, value in sorted(context_dict.items()):
            serialized[key] = serialize_object(value, depth=0)

        json_str = json.dumps(serialized, indent=2, ensure_ascii=False)
        self.stdout.write(json_str)
        self.stdout.write("\n" + "=" * 80 + "\n")

    def _output_template_format(self, context_dict, max_depth):
        """模板风格输出 - 显示所有可用的模板变量"""

        def format_value(obj, depth=0):
            """格式化值用于模板风格显示"""
            if depth >= max_depth:
                return f"<{type(obj).__name__}>"

            # 基本类型
            if isinstance(obj, str | int | float | bool | type(None)):
                return repr(obj)

            # 列表类型
            if isinstance(obj, list | tuple):
                if len(obj) == 0:
                    return "[]"

                # 如果是简单类型列表，直接显示前5个
                if isinstance(obj[0], str | int | float | bool | type(None)):
                    items = [repr(item) for item in obj[:5]]
                    if len(obj) > 5:
                        items.append(f"... ({len(obj) - 5} more)")
                    return f"[{', '.join(items)}]"
                else:
                    return f"[{type(obj[0]).__name__} × {len(obj)}]"

            # 字典类型
            if isinstance(obj, dict):
                if len(obj) == 0:
                    return "{}"

                items = list(obj.items())

                # 尝试将所有键值对格式化，看看总长度
                pairs = []
                for k, v in items:
                    # 格式化值
                    if isinstance(v, str):
                        v_repr = repr(v)
                    elif isinstance(v, int | float | bool | type(None)):
                        v_repr = repr(v)
                    elif isinstance(v, list | tuple):
                        if len(v) == 0:
                            v_repr = "[]"
                        elif len(v) <= 2 and all(isinstance(x, str | int | float | bool | type(None)) for x in v):
                            v_repr = repr(v)
                        else:
                            v_repr = f"[{len(v)} items]"
                    elif isinstance(v, dict):
                        v_repr = f"{{{len(v)} items}}"
                    else:
                        v_repr = f"<{type(v).__name__}>"

                    # 截断过长的值
                    if len(v_repr) > 50:
                        v_repr = v_repr[:47] + "..."

                    pairs.append(f"'{k}': {v_repr}")

                # 拼接所有键值对
                dict_content = ", ".join(pairs)

                # 如果总长度超过150字符，只显示前几个
                if len(dict_content) > 150:
                    # 只显示前3个键值对
                    short_pairs = pairs[:3]
                    short_pairs.append(f"... +{len(items) - 3} more")
                    return f"{{{', '.join(short_pairs)}}}"
                else:
                    # 完整显示
                    return f"{{{dict_content}}}"

            # 对象类型 - 返回类型名
            return f"<{type(obj).__name__}>"

        def collect_variables(obj, prefix="", depth=0, variables=None):
            """递归收集所有可用的模板变量"""
            if variables is None:
                variables = []

            if depth >= max_depth:
                return variables

            # 字典类型：只显示字典本身，不展开子键
            if isinstance(obj, dict):
                # 字典作为整体显示，不递归展开其内部的键
                # 内容格式已经在 format_value 中处理
                return variables

            # 对象类型
            try:
                attrs = [attr for attr in dir(obj) if not attr.startswith("_") and attr != "parent"]
                for attr in attrs[:30]:
                    try:
                        value = getattr(obj, attr)
                        if not callable(value):
                            var_path = f"{prefix}.{attr}" if prefix else attr

                            if isinstance(value, str | int | float | bool | type(None) | list | tuple | dict):
                                # 简单类型、列表、字典：直接显示，不递归
                                variables.append((var_path, format_value(value, depth)))
                            else:
                                # 其他对象类型：递归展开属性
                                collect_variables(value, var_path, depth + 1, variables)
                    except Exception:
                        pass
            except Exception:
                pass

            return variables

        # 收集所有变量（过滤掉 parent 相关）
        all_variables = []

        for key in sorted(context_dict.keys()):
            if key == "parent":  # 跳过顶级的 parent（如果有）
                continue
            value = context_dict[key]
            variables = collect_variables(value, key, depth=0)
            all_variables.extend(variables)

        # 输出模板变量
        self.stdout.write(self.style.SUCCESS("\n可用的模板变量：\n"))

        if all_variables:
            max_var_length = max(len(var) for var, _ in all_variables)
            for var_path, value_str in all_variables:
                # 限制值的长度
                if len(value_str) > 80:
                    value_str = value_str[:77] + "..."
                self.stdout.write(f"{{{{ {var_path:<{max_var_length}} }}}} -> {value_str}")

        self.stdout.write(f"\n总计 {len(all_variables)} 个可用变量")
        self.stdout.write("\n" + "=" * 80 + "\n")

    def _output_single_variable(self, context_dict, variable_path, alert_id, action_instance):
        """查询并输出单个模板变量的值"""
        # 保存原始输入用于显示
        original_input = variable_path.strip()

        # 清理变量路径：移除模板语法的花括号
        variable_path = original_input

        # 移除 Jinja2 模板语法的花括号
        # {{ variable }} -> variable
        if variable_path.startswith("{{") and variable_path.endswith("}}"):
            variable_path = variable_path[2:-2].strip()
        # 单花括号通常是误用，但为了容错也支持
        # 但要避免误伤嵌套的方括号，如 {a[0]}
        elif variable_path.startswith("{") and variable_path.endswith("}"):
            # 检查是否真的是模板语法而不是字典/集合字面量
            inner = variable_path[1:-1].strip()
            # 简单启发式：如果不包含逗号或冒号，很可能是模板变量
            if ":" not in inner and "," not in inner:
                variable_path = inner

        def get_nested_value(obj, path):
            """通过路径获取嵌套对象的值.

            模拟 Jinja2 的变量访问机制，支持点号访问、方括号索引、混合使用等。

            支持格式：

            - ``a.b.c`` - 点号访问
            - ``a[0]`` - 方括号数字索引
            - ``a['key']`` 或 ``a["key"]`` - 方括号字符串键
            - ``a.0`` - 点号数字索引（Jinja2 兼容）
            - ``a.b[0].c['key']`` - 混合使用

            :param obj: 要访问的对象
            :param path: 变量路径
            :return: (value, error_message) 元组
            """
            import re

            # 使用正则表达式拆分路径，支持 a.b[0].c['key'] 等格式
            # 匹配: 普通标识符、点号、方括号内容
            pattern = r"\.?([^\.\[]+|\[[^\]]+\])"
            matches = re.findall(pattern, path)

            parts = []
            for match in matches:
                if match.startswith("["):
                    # 保持方括号内容
                    parts.append(match)
                else:
                    # 普通标识符，去除前导点号
                    parts.append(match)

            # 遍历路径
            current = obj

            for part in parts:
                # 处理方括号访问 [xxx]
                if part.startswith("[") and part.endswith("]"):
                    bracket_content = part[1:-1]  # 去掉方括号

                    # 尝试1: 数字索引 [0], [1]
                    if bracket_content.isdigit():
                        try:
                            index = int(bracket_content)
                            if not isinstance(current, list | tuple):
                                return None, f"{type(current).__name__} 不是列表，无法使用数字索引 {part}"
                            if index < 0 or index >= len(current):
                                return None, f"索引 {index} 超出范围（列表长度：{len(current)}）"
                            current = current[index]
                            continue
                        except ValueError:
                            pass

                    # 尝试2: 字符串键 ['key'] 或 ["key"]
                    # 去掉引号
                    if (bracket_content.startswith("'") and bracket_content.endswith("'")) or (
                        bracket_content.startswith('"') and bracket_content.endswith('"')
                    ):
                        key = bracket_content[1:-1]  # 去掉引号
                    else:
                        # 没有引号的情况，直接作为键
                        key = bracket_content

                    # 访问字典键或对象属性
                    if isinstance(current, dict):
                        if key not in current:
                            return None, f"字典中不存在键 '{key}'"
                        current = current[key]
                    elif hasattr(current, key):
                        current = getattr(current, key)
                    else:
                        return None, f"无法访问 {type(current).__name__}['{key}']"
                    continue

                # Jinja2 的访问逻辑（与 Jinja2 保持一致）：
                # 1. 如果是字典，尝试作为键访问
                # 2. 如果是对象，尝试作为属性访问
                # 3. 如果是列表且 part 是数字，尝试作为索引访问

                # 尝试 1：字典键访问
                if isinstance(current, dict):
                    if part in current:
                        current = current[part]
                        continue
                    else:
                        return None, f"字典中不存在键 '{part}'"

                # 尝试 2：对象属性访问
                if hasattr(current, part):
                    current = getattr(current, part)
                    continue

                # 尝试 3：列表数字索引访问（Jinja2 兼容：list.0 等同于 list[0]）
                if isinstance(current, list | tuple) and part.isdigit():
                    index = int(part)
                    if index < 0 or index >= len(current):
                        return None, f"索引 {index} 超出范围（列表长度：{len(current)}）"
                    current = current[index]
                    continue

                # 都失败了
                return None, f"无法访问 {type(current).__name__}.{part}"

            return current, None

        def format_detailed_value(obj, indent=0):
            """详细格式化值"""
            prefix = "  " * indent
            lines = []

            # 基本类型
            if isinstance(obj, str | int | float | bool | type(None)):
                lines.append(f"{prefix}{repr(obj)}")
                return lines

            # 列表类型
            if isinstance(obj, list | tuple):
                if len(obj) == 0:
                    lines.append(f"{prefix}[]")
                    return lines

                lines.append(f"{prefix}[")
                # 显示前10个元素
                for i, item in enumerate(obj[:10]):
                    if isinstance(item, str | int | float | bool | type(None)):
                        lines.append(f"{prefix}  {repr(item)},")
                    elif isinstance(item, dict):
                        # 字典元素：显示摘要
                        if len(item) == 0:
                            lines.append(f"{prefix}  {{}},")
                        else:
                            # 显示前3个键值对
                            dict_pairs = []
                            for k, v in list(item.items())[:3]:
                                v_repr = (
                                    repr(v)
                                    if isinstance(v, str | int | float | bool | type(None))
                                    else f"<{type(v).__name__}>"
                                )
                                if len(v_repr) > 30:
                                    v_repr = v_repr[:27] + "..."
                                dict_pairs.append(f"'{k}': {v_repr}")

                            if len(item) > 3:
                                dict_pairs.append(f"... +{len(item) - 3} more")

                            lines.append(f"{prefix}  {{{', '.join(dict_pairs)}}},")
                    elif isinstance(item, list | tuple):
                        # 嵌套列表
                        lines.append(f"{prefix}  [{len(item)} items],")
                    else:
                        lines.append(f"{prefix}  <{type(item).__name__}>,")

                if len(obj) > 10:
                    lines.append(f"{prefix}  ... ({len(obj) - 10} more items)")
                lines.append(f"{prefix}]")
                lines.append(f"{prefix}总计: {len(obj)} 个元素")
                return lines

            # 字典类型
            if isinstance(obj, dict):
                if len(obj) == 0:
                    lines.append(f"{prefix}{{}}")
                    return lines

                lines.append(f"{prefix}{{")
                for i, (key, value) in enumerate(list(obj.items())[:10]):
                    # 格式化值
                    if isinstance(value, str | int | float | bool | type(None)):
                        value_repr = repr(value)
                    elif isinstance(value, dict):
                        if len(value) == 0:
                            value_repr = "{}"
                        else:
                            # 显示前2个键
                            keys = list(value.keys())[:2]
                            key_str = ", ".join(f"'{k}'" for k in keys)
                            if len(value) > 2:
                                value_repr = f"{{{len(value)} items: {key_str}, ...}}"
                            else:
                                value_repr = f"{{{len(value)} items: {key_str}}}"
                    elif isinstance(value, list | tuple):
                        if len(value) == 0:
                            value_repr = "[]"
                        else:
                            value_repr = f"[{len(value)} items]"
                    else:
                        value_repr = f"<{type(value).__name__}>"

                    if len(value_repr) > 60:
                        value_repr = value_repr[:57] + "..."
                    lines.append(f"{prefix}  {key}: {value_repr}")

                if len(obj) > 10:
                    lines.append(f"{prefix}  ... ({len(obj) - 10} more items)")
                lines.append(f"{prefix}}}")
                return lines

            # 对象类型
            lines.append(f"{prefix}<{type(obj).__name__}>")
            try:
                attrs = [attr for attr in dir(obj) if not attr.startswith("_")]
                for attr in attrs[:10]:
                    try:
                        value = getattr(obj, attr)
                        if not callable(value):
                            value_repr = (
                                repr(value)
                                if isinstance(value, str | int | float | bool | type(None))
                                else f"<{type(value).__name__}>"
                            )
                            if len(value_repr) > 60:
                                value_repr = value_repr[:57] + "..."
                            lines.append(f"{prefix}  .{attr}: {value_repr}")
                    except Exception:
                        pass
            except Exception:
                pass

            return lines

        # 输出头部
        self.stdout.write(self.style.SUCCESS("=" * 80))
        self.stdout.write(self.style.SUCCESS("模板变量查询"))
        self.stdout.write(self.style.SUCCESS("=" * 80 + "\n"))
        self.stdout.write(f"告警 ID: {alert_id}")
        self.stdout.write(f"动作实例 ID: {action_instance.id}")

        # 显示查询变量（使用原始输入以保留引号等）
        if original_input.strip().startswith("{{"):
            self.stdout.write(f"查询变量: {original_input}")
        else:
            self.stdout.write(f"查询变量: {{{{ {original_input} }}}}")

        self.stdout.write("\n" + "-" * 80 + "\n")

        # 获取变量值
        value, error = get_nested_value(context_dict, variable_path)

        if error:
            self.stdout.write(self.style.ERROR(f"❌ 变量不存在: {error}\n"))
            self.stdout.write(self.style.WARNING("提示: 使用不带 --variable 参数运行命令查看所有可用变量"))
            return

        # 输出变量信息
        self.stdout.write(self.style.SUCCESS(f"✓ 变量类型: {type(value).__name__}"))
        self.stdout.write(self.style.SUCCESS("\n变量值:\n"))

        # 详细输出值
        for line in format_detailed_value(value):
            self.stdout.write(line)

        self.stdout.write("\n" + "=" * 80 + "\n")
