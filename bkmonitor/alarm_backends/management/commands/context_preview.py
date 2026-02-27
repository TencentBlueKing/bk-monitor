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
from bkmonitor.utils.template import Jinja2Renderer, NoticeRowRenderer

logger = logging.getLogger("fta_action.run")

# 尝试导入 elasticsearch_dsl 的类型
try:
    from elasticsearch_dsl.utils import AttrList, AttrDict
except ImportError:
    # 如果导入失败，定义占位符类用于类型检查
    class AttrList(list):
        pass

    class AttrDict(dict):
        pass


class Command(BaseCommand):
    """告警上下文变量预览命令.

    预览告警通知模板中可用的上下文变量及其结构。

    架构设计
    --------
    本命令采用分层设计，将数据获取、格式化、输出等逻辑分离：

    - 数据层：_get_action_instance, _get_alert_documents
    - 转换层：_normalize_es_dsl_object（统一处理elasticsearch_dsl对象）
    - 格式化层：_serialize_value, _format_value_for_template, _format_detailed_value
    - 输出层：_output_* 系列方法

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

    输出截断原则
    ------------
    为了平衡可读性和完整性，本命令采用以下输出策略：

    - **指定变量查询**（使用 ``--variable`` 参数）：

      - **单个变量查询**：使用 ``_format_detailed_value`` 方法

        - **完全展开**：递归显示所有嵌套结构（最大深度 5 层）
        - **不截断**：字符串值完整输出，不限制长度
        - **完整性**：显示所有列表元素和字典键值对
        - **多行格式**：便于阅读复杂结构

      - **批量变量查询**：使用 ``_format_value_for_batch`` 方法

        - **完整输出**：不限制字符串长度、键值对数量
        - **适度递归**：递归深度限制为 3 层（避免过深）
        - **单行格式**：便于快速浏览多个变量
        - **不截断**：确保用户能看到完整数据

    - **列出所有变量**（不使用 ``--variable`` 参数）：

      - 使用 ``_format_value_for_template`` 方法
      - **适度截断**：保持输出可读性
      - 列表显示前 5-10 个元素
      - 字典显示前 3 个键值对（总长度超过 150 字符时）
      - 字符串值限制在 50 字符
      - 递归深度限制为 2 层

    这样设计的原因：

    - 指定变量时（单个或批量），用户需要查看完整数据以便调试
    - 列出所有变量时，需要概览性信息而非详细内容

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
        6. 批量查询：使用半角逗号分隔多个变量，如 ``alert.id,alert.name,target.host.ip``

        .. warning::
           Shell 转义注意事项：

           - 务必用双引号包裹整个参数：``--variable "path.to[0]['key']"``
           - 或使用更简单的点号语法：``--variable "path.to[0].key"``
           - 批量查询时：``--variable "alert.id,alert.name,target.host.ip"``

    :param depth: 递归深度（可选，默认为2，最大为3）
    :param format: 输出格式（可选，template=模板风格[默认]，json=JSON格式）

    示例
    ----
    1. 预览所有可用的模板变量（默认模板风格）::

        python manage.py context_preview 12345

    输出示例::

        可用的模板变量：
        {{ target.business.bk_biz_name        }} -> '蓝鲸'
        {{ target.business.bk_alarm_rvc_man   }} -> ['admin', 'operator']
        {{ alarm.alert_name                   }} -> '磁盘空间不足'
        {{ alarm.dimensions                   }} -> {'ip': '10.0.0.1', 'bk_cloud_id': '0'}
        总计 156 个可用变量

    2. 查询指定模板变量的值::

        python manage.py context_preview 12345 --variable "target.business.bk_alarm_rvc_man"
        # 或直接复制模板格式（带花括号）
        python manage.py context_preview 12345 --variable "{{ target.business.bk_alarm_rvc_man }}"

    3. 批量查询多个变量（使用半角逗号分隔）::

        python manage.py context_preview 12345 --variable "alert.id,alert.name,target.host.ip"
        python manage.py context_preview 12345 --variable "{{ alert.id }},{{ alert.name }},{{ target.host.ip }}"

    4. 支持各种访问方式（与 Jinja2 模板完全一致）::

        python manage.py context_preview 12345 --variable "strategy.item.query_configs[0]"
        python manage.py context_preview 12345 --variable "strategy.item.query_configs.0"  # 等价于 [0]
        python manage.py context_preview 12345 --variable "alarm.dimensions['ip'].display_value"
    """

    @staticmethod
    def _normalize_es_dsl_object(obj):
        """将elasticsearch_dsl的数据结构转换为标准Python类型.

        统一处理AttrList和AttrDict对象，避免在多处重复相同逻辑。

        :param obj: 待转换对象
        :return: 标准Python类型（list或dict）
        """
        if isinstance(obj, AttrList):
            return list(obj)
        if isinstance(obj, AttrDict):
            # 使用to_dict()方法转换，这是AttrDict的标准方法
            try:
                return obj.to_dict()
            except (AttributeError, TypeError):
                # 如果to_dict()不可用，fallback到其他方式
                try:
                    return dict(obj.items())
                except (AttributeError, TypeError):
                    try:
                        return {k: obj[k] for k in obj.keys()}
                    except (AttributeError, TypeError):
                        return dict(obj)
        return obj

    def add_arguments(self, parser):
        parser.add_argument("alert_id", type=int, help="告警 ID")
        parser.add_argument("--action-id", type=int, help="动作实例 ID（可选）")
        parser.add_argument(
            "--variable",
            type=str,
            help="指定要查询的模板变量，支持完整 Jinja2 格式：'var.path'、'list[0]'、'dict[\"key\"]'。支持批量查询（用半角逗号分隔）",
        )
        parser.add_argument("--depth", type=int, default=2, help="递归深度（默认2，最大3）")
        parser.add_argument("--format", type=str, default="template", choices=["template", "json"], help="输出格式")

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

            # 4. 如果指定了变量，查询该变量（支持批量）
            if variable:
                # 支持批量查询：通过半角逗号分隔多个变量
                variable_paths = [v.strip() for v in variable.split(",") if v.strip()]
                if len(variable_paths) == 1:
                    # 单个变量查询
                    self._output_single_variable(context_dict, variable_paths[0], alert_id, action_instance, context)
                else:
                    # 批量变量查询
                    self._output_batch_variables(context_dict, variable_paths, alert_id, action_instance, context)
                return

            # 5. 否则输出所有变量
            self._output_header(alert_id, action_instance, len(alert_docs))

            if output_format == "json":
                self._output_json_format(context_dict, depth)
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
        """输出头部信息.

        :param alert_id: 告警ID
        :param action_instance: 动作实例
        :param alert_count: 关联告警数
        """
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 80))
        self.stdout.write(self.style.SUCCESS("告警上下文变量预览"))
        self.stdout.write(self.style.SUCCESS("=" * 80 + "\n"))

        self.stdout.write(f"告警 ID: {alert_id}")
        self.stdout.write(f"动作实例 ID: {action_instance.id}")
        self.stdout.write(f"关联告警数: {alert_count}")
        self.stdout.write("\n" + "-" * 80 + "\n")

    def _serialize_value(self, obj, depth=0, max_depth=2):
        """序列化对象为JSON可序列化的格式.

        统一的值序列化逻辑，用于JSON格式输出。

        :param obj: 要序列化的对象
        :param depth: 当前递归深度
        :param max_depth: 最大递归深度
        :return: 可JSON序列化的对象
        """
        if depth >= max_depth:
            return f"<{type(obj).__name__}>"

        # 规范化elasticsearch_dsl对象
        obj = self._normalize_es_dsl_object(obj)

        if isinstance(obj, str | int | float | bool | type(None)):
            return obj

        if isinstance(obj, dict):
            return {k: self._serialize_value(v, depth + 1, max_depth) for k, v in list(obj.items())[:20]}

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
                result = [self._serialize_value(item, depth + 1, max_depth) for item in obj[:5]]
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
                        result[attr] = self._serialize_value(value, depth + 1, max_depth)
                except Exception:
                    pass
            return result
        except Exception:
            return f"<{type(obj).__name__}>"

    def _output_json_format(self, context_dict, max_depth):
        """JSON格式输出.

        :param context_dict: 上下文字典
        :param max_depth: 最大递归深度
        """
        import json

        serialized = {}
        for key, value in sorted(context_dict.items()):
            serialized[key] = self._serialize_value(value, depth=0, max_depth=max_depth)

        json_str = json.dumps(serialized, indent=2, ensure_ascii=False)
        self.stdout.write(json_str)
        self.stdout.write("\n" + "=" * 80 + "\n")

    def _format_value_for_template(self, obj, depth=0, max_depth=2):
        """格式化值用于模板风格显示.

        统一的模板格式化逻辑，用于模板风格输出。

        :param obj: 要格式化的对象
        :param depth: 当前递归深度
        :param max_depth: 最大递归深度
        :return: 格式化后的字符串
        """
        if depth >= max_depth:
            return f"<{type(obj).__name__}>"

        # 规范化elasticsearch_dsl对象
        obj = self._normalize_es_dsl_object(obj)

        # 基本类型
        if isinstance(obj, str | int | float | bool | type(None)):
            return repr(obj)

        # 列表类型（包括AttrList，已转换为list）
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

    def _format_value_for_batch(self, obj, depth=0, max_depth=3):
        """格式化值用于批量查询 - 完整输出，不截断.

        用于批量变量查询时的输出，确保用户能看到完整数据。

        **输出原则**：

        - **完整输出**：不限制字符串长度、键值对数量
        - **适度递归**：递归深度限制为 3 层（避免过深）
        - **简洁格式**：使用单行格式，便于快速浏览

        :param obj: 要格式化的对象
        :param depth: 当前递归深度
        :param max_depth: 最大递归深度
        :return: 格式化后的字符串
        """
        if depth >= max_depth:
            return f"<{type(obj).__name__}>"

        # 规范化elasticsearch_dsl对象
        obj = self._normalize_es_dsl_object(obj)

        # 基本类型
        if isinstance(obj, str | int | float | bool | type(None)):
            return repr(obj)

        # 列表类型
        if isinstance(obj, list | tuple):
            if len(obj) == 0:
                return "[]"

            # 如果是简单类型列表，完整显示所有元素
            if isinstance(obj[0], str | int | float | bool | type(None)):
                items = [repr(item) for item in obj]
                return f"[{', '.join(items)}]"
            else:
                # 复杂类型列表，递归格式化所有元素
                items = [self._format_value_for_batch(item, depth + 1, max_depth) for item in obj]
                return f"[{', '.join(items)}]"

        # 字典类型 - 完整输出所有键值对，不截断
        if isinstance(obj, dict):
            if len(obj) == 0:
                return "{}"

            pairs = []
            for k, v in obj.items():
                # 递归格式化值
                if isinstance(v, str):
                    v_repr = repr(v)
                elif isinstance(v, int | float | bool | type(None)):
                    v_repr = repr(v)
                elif isinstance(v, list | tuple):
                    if len(v) == 0:
                        v_repr = "[]"
                    elif len(v) <= 3 and all(isinstance(x, str | int | float | bool | type(None)) for x in v):
                        v_repr = repr(v)
                    else:
                        # 递归格式化列表
                        v_repr = self._format_value_for_batch(v, depth + 1, max_depth)
                elif isinstance(v, dict):
                    # 递归格式化字典
                    v_repr = self._format_value_for_batch(v, depth + 1, max_depth)
                else:
                    v_repr = f"<{type(v).__name__}>"

                # 不截断，完整输出
                pairs.append(f"'{k}': {v_repr}")

            # 完整显示所有键值对
            return f"{{{', '.join(pairs)}}}"

        # 对象类型 - 返回类型名
        return f"<{type(obj).__name__}>"

    def _output_template_format(self, context_dict, max_depth):
        """模板风格输出 - 显示所有可用的模板变量.

        :param context_dict: 上下文字典
        :param max_depth: 最大递归深度
        """

        def collect_variables(obj, prefix="", depth=0, variables=None):
            """递归收集所有可用的模板变量.

            :param obj: 要收集的对象
            :param prefix: 变量路径前缀
            :param depth: 当前递归深度
            :param variables: 变量列表（累积结果）
            :return: 变量列表
            """
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
                                variables.append((var_path, self._format_value_for_template(value, depth, max_depth)))
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

    def _format_detailed_value(self, obj, indent=0, max_depth=5):
        """详细格式化值 - 完全展开，不截断任何内容.

        用于单个变量查询时的详细输出。

        **输出原则**：

        - **完全展开**：递归显示所有嵌套结构
        - **不截断**：不限制字符串长度、列表元素数、字典键值对数
        - **完整性**：确保用户能看到变量的完整数据

        :param obj: 要格式化的对象
        :param indent: 当前缩进级别
        :param max_depth: 最大递归深度（防止无限递归，默认5层）
        :return: 格式化后的行列表
        """
        prefix = "  " * indent
        lines = []

        # 防止无限递归
        if indent >= max_depth:
            lines.append(f"{prefix}<max depth reached>")
            return lines

        # 规范化elasticsearch_dsl对象（在格式化前转换）
        obj = self._normalize_es_dsl_object(obj)

        # 基本类型
        if isinstance(obj, str | int | float | bool | type(None)):
            lines.append(f"{prefix}{repr(obj)}")
            return lines

        # 列表类型 - 完全展开所有元素（包括已转换的AttrList）
        if isinstance(obj, list | tuple):
            if len(obj) == 0:
                lines.append(f"{prefix}[]")
                return lines

            lines.append(f"{prefix}[")
            # 显示所有元素，不省略
            for i, item in enumerate(obj):
                # 先规范化元素（将AttrDict/AttrList转换为标准类型）
                item = self._normalize_es_dsl_object(item)
                
                if isinstance(item, str | int | float | bool | type(None)):
                    lines.append(f"{prefix}  {repr(item)},")
                elif isinstance(item, dict):
                    # 字典元素：递归展开
                    if len(item) == 0:
                        lines.append(f"{prefix}  {{}},")
                    else:
                        lines.append(f"{prefix}  {{")
                        # 递归显示所有键值对
                        for k, v in item.items():
                            # 规范化值
                            v = self._normalize_es_dsl_object(v)
                            if isinstance(v, str | int | float | bool | type(None)):
                                lines.append(f"{prefix}    '{k}': {repr(v)},")
                            else:
                                # 递归格式化嵌套结构
                                nested_lines = self._format_detailed_value(v, indent + 2, max_depth)
                                # 将第一行的键名合并
                                if nested_lines:
                                    first_line = nested_lines[0].lstrip()
                                    lines.append(f"{prefix}    '{k}': {first_line}")
                                    # 添加其余行（调整缩进）
                                    for nested_line in nested_lines[1:]:
                                        lines.append(f"{prefix}      {nested_line.lstrip()}")
                                else:
                                    lines.append(f"{prefix}    '{k}': <{type(v).__name__}>,")
                        lines.append(f"{prefix}  }},")
                elif isinstance(item, list | tuple):
                    # 嵌套列表：递归展开（已在循环开始时规范化）
                    nested_lines = self._format_detailed_value(item, indent + 1, max_depth)
                    if nested_lines:
                        # 嵌套列表的第一行已经有正确的缩进（indent + 1），直接添加
                        # 最后一行如果是`]`或`总计:`，需要添加逗号
                        for idx, nested_line in enumerate(nested_lines):
                            if idx == len(nested_lines) - 1:
                                # 最后一行：如果是`]`或`总计:`，添加逗号
                                stripped = nested_line.strip()
                                if stripped.endswith("]") or stripped.startswith("总计"):
                                    lines.append(nested_line + ",")
                                else:
                                    lines.append(nested_line)
                            else:
                                lines.append(nested_line)
                    else:
                        # 空列表
                        lines.append(f"{prefix}  [],")
                else:
                    lines.append(f"{prefix}  <{type(item).__name__}>,")

            lines.append(f"{prefix}]")
            lines.append(f"{prefix}总计: {len(obj)} 个元素")
            return lines

        # 字典类型 - 完全展开所有键值对（包括AttrDict，已转换为dict）
        if isinstance(obj, dict):
            if len(obj) == 0:
                lines.append(f"{prefix}{{}}")
                return lines

            lines.append(f"{prefix}{{")
            # 显示所有键值对，不省略
            for key, value in obj.items():
                # 规范化值（处理嵌套的elasticsearch_dsl对象）
                value = self._normalize_es_dsl_object(value)
                # 格式化值（指定变量查询时不截断）
                if isinstance(value, str | int | float | bool | type(None)):
                    value_repr = repr(value)
                    lines.append(f"{prefix}  {key}: {value_repr}")
                elif isinstance(value, dict):
                    # 嵌套字典：递归展开
                    nested_lines = self._format_detailed_value(value, indent + 2, max_depth)
                    if nested_lines:
                        # 第一行是`{`，需要加上key前缀
                        first_line = nested_lines[0].lstrip()
                        lines.append(f"{prefix}  {key}: {first_line}")
                        # 添加其余行
                        for nested_line in nested_lines[1:]:
                            lines.append(nested_line)
                    else:
                        lines.append(f"{prefix}  {key}: {{}}")
                elif isinstance(value, list | tuple):
                    # 嵌套列表：递归展开（包括AttrList，已转换为list）
                    nested_lines = self._format_detailed_value(value, indent + 2, max_depth)
                    if nested_lines:
                        # 第一行是`[`，需要加上key前缀
                        first_line = nested_lines[0].lstrip()
                        lines.append(f"{prefix}  {key}: {first_line}")
                        # 添加其余行
                        for nested_line in nested_lines[1:]:
                            lines.append(nested_line)
                    else:
                        lines.append(f"{prefix}  {key}: []")
                else:
                    value_repr = f"<{type(value).__name__}>"
                    lines.append(f"{prefix}  {key}: {value_repr}")

            lines.append(f"{prefix}}}")
            return lines

        # 对象类型
        lines.append(f"{prefix}<{type(obj).__name__}>")
        try:
            attrs = [attr for attr in dir(obj) if not attr.startswith("_")]
            # 显示所有属性，不省略
            for attr in attrs:
                try:
                    value = getattr(obj, attr)
                    if not callable(value):
                        if isinstance(value, str | int | float | bool | type(None)):
                            value_repr = repr(value)
                            lines.append(f"{prefix}  .{attr}: {value_repr}")
                        else:
                            # 对于复杂类型，显示类型信息
                            lines.append(f"{prefix}  .{attr}: <{type(value).__name__}>")
                except Exception:
                    pass
        except Exception:
            pass

        return lines

    def _output_single_variable(self, context_dict, variable_path, alert_id, action_instance, context=None):
        """查询并输出单个模板变量的值.

        :param context_dict: 上下文字典
        :param variable_path: 变量路径
        :param alert_id: 告警ID
        :param action_instance: 动作实例
        :param context: ActionContext对象（用于渲染模板）
        """
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
        for line in self._format_detailed_value(value):
            self.stdout.write(line)

        # 如果变量包含点号（如 content.receivers），显示基于处理套餐逻辑的渲染结果
        if "." in variable_path and context is not None:
            try:
                # 构建模板字符串
                template_str = f"{{{{ {variable_path} }}}}"

                # 获取 context 字典（与处理套餐的 get_context() 逻辑一致）
                render_context = context.get_dictionary()

                # 模拟处理套餐的 jinja_render 逻辑（与 CommonActionProcessor.jinja_render 完全一致）
                # 1. 先渲染 user_content（如果有 default_content_template）
                user_content = Jinja2Renderer.render(render_context.get("default_content_template", ""), render_context)
                alarm_content = NoticeRowRenderer.render(user_content, render_context)
                render_context["user_content"] = alarm_content

                # 2. 渲染模板值（与处理套餐的渲染逻辑完全一致）
                rendered_result = Jinja2Renderer.render(template_str, render_context)

                plugin_type = action_instance.action_plugin.get("plugin_type")
                plugin_type_name = plugin_type if plugin_type else "未知"

                self.stdout.write("\n" + "-" * 80)
                self.stdout.write(self.style.SUCCESS("📝 模板渲染结果（基于处理套餐实际渲染逻辑）:"))
                self.stdout.write(self.style.SUCCESS(f"套餐类型: {plugin_type_name}"))
                self.stdout.write(self.style.SUCCESS(f"模板: {template_str}"))
                self.stdout.write(self.style.SUCCESS(f"渲染结果: {repr(rendered_result)}"))
                self.stdout.write("-" * 80)
            except Exception as e:
                # 渲染失败时，记录详细错误信息，不影响主流程
                import traceback

                self.stdout.write("\n" + "-" * 80)
                self.stdout.write(self.style.WARNING(f"⚠️  渲染失败: {str(e)}"))
                self.stdout.write(self.style.WARNING(f"错误详情: {traceback.format_exc()}"))
                self.stdout.write("-" * 80)

        self.stdout.write("\n" + "=" * 80 + "\n")

    def _output_batch_variables(self, context_dict, variable_paths, alert_id, action_instance, context=None):
        """批量查询并输出多个模板变量的值.

        :param context_dict: 上下文字典
        :param variable_paths: 变量路径列表
        :param alert_id: 告警ID
        :param action_instance: 动作实例
        :param context: ActionContext对象（用于渲染模板）
        """
        # 输出头部
        self.stdout.write(self.style.SUCCESS("=" * 80))
        self.stdout.write(self.style.SUCCESS("批量模板变量查询"))
        self.stdout.write(self.style.SUCCESS("=" * 80 + "\n"))
        self.stdout.write(f"告警 ID: {alert_id}")
        self.stdout.write(f"动作实例 ID: {action_instance.id}")
        self.stdout.write(f"查询变量数: {len(variable_paths)}")
        self.stdout.write("\n" + "-" * 80 + "\n")

        # 定义嵌套函数用于获取变量值（复用 _output_single_variable 中的逻辑）
        def get_nested_value(obj, path):
            """通过路径获取嵌套对象的值.

            模拟 Jinja2 的变量访问机制，支持点号访问、方括号索引、混合使用等。

            :param obj: 要访问的对象
            :param path: 变量路径
            :return: (value, error_message) 元组
            """
            import re

            # 使用正则表达式拆分路径，支持 a.b[0].c['key'] 等格式
            pattern = r"\.?([^\.\[]+|\[[^\]]+\])"
            matches = re.findall(pattern, path)

            parts = []
            for match in matches:
                if match.startswith("["):
                    parts.append(match)
                else:
                    parts.append(match)

            # 遍历路径
            current = obj

            for part in parts:
                # 处理方括号访问 [xxx]
                if part.startswith("[") and part.endswith("]"):
                    bracket_content = part[1:-1]

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
                    if (bracket_content.startswith("'") and bracket_content.endswith("'")) or (
                        bracket_content.startswith('"') and bracket_content.endswith('"')
                    ):
                        key = bracket_content[1:-1]
                    else:
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

                # Jinja2 的访问逻辑
                if isinstance(current, dict):
                    if part in current:
                        current = current[part]
                        continue
                    else:
                        return None, f"字典中不存在键 '{part}'"

                if hasattr(current, part):
                    current = getattr(current, part)
                    continue

                if isinstance(current, list | tuple) and part.isdigit():
                    index = int(part)
                    if index < 0 or index >= len(current):
                        return None, f"索引 {index} 超出范围（列表长度：{len(current)}）"
                    current = current[index]
                    continue

                return None, f"无法访问 {type(current).__name__}.{part}"

            return current, None

        # 清理变量路径（移除模板语法的花括号）
        def clean_variable_path(var_path):
            """清理变量路径，移除模板语法的花括号."""
            var_path = var_path.strip()
            if var_path.startswith("{{") and var_path.endswith("}}"):
                var_path = var_path[2:-2].strip()
            elif var_path.startswith("{") and var_path.endswith("}"):
                inner = var_path[1:-1].strip()
                if ":" not in inner and "," not in inner:
                    var_path = inner
            return var_path

        # 批量查询所有变量
        results = []
        for original_path in variable_paths:
            cleaned_path = clean_variable_path(original_path)
            value, error = get_nested_value(context_dict, cleaned_path)
            results.append({
                "original": original_path,
                "cleaned": cleaned_path,
                "value": value,
                "error": error,
            })

        # 输出结果
        for idx, result in enumerate(results, 1):
            self.stdout.write(f"\n[{idx}/{len(results)}] 变量: {{{{ {result['cleaned']} }}}}")
            self.stdout.write("-" * 80)

            if result["error"]:
                self.stdout.write(self.style.ERROR(f"❌ 变量不存在: {result['error']}"))
            else:
                value = result["value"]
                self.stdout.write(self.style.SUCCESS(f"✓ 类型: {type(value).__name__}"))
                
                # 格式化输出值（批量查询时完整输出，不截断）
                formatted_value = self._format_value_for_batch(value, depth=0, max_depth=3)
                self.stdout.write(f"值: {formatted_value}")

        # 输出汇总信息
        self.stdout.write("\n" + "=" * 80)
        success_count = sum(1 for r in results if not r["error"])
        error_count = len(results) - success_count
        self.stdout.write(self.style.SUCCESS(f"查询完成: 成功 {success_count} 个，失败 {error_count} 个"))
        
        if error_count > 0:
            self.stdout.write(self.style.WARNING("\n提示: 使用不带 --variable 参数运行命令查看所有可用变量"))
        
        self.stdout.write("=" * 80 + "\n")
