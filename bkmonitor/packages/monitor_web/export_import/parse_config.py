"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import abc
import json
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import yaml
from bk_monitor_base.strategy import StrategySerializer
from django.utils.translation import gettext as _
from rest_framework.exceptions import ErrorDetail, ValidationError

from bkmonitor.utils.request import get_request_tenant_id, get_request_username
from core.errors.plugin import PluginParseError
from monitor_web.export_import.constant import ImportDetailStatus
from monitor_web.models import CollectConfigMeta, CollectorPluginMeta, Signature
from monitor_web.plugin.manager import PluginManagerFactory

logger = logging.getLogger("monitor_web")

_USE_BASE_PLUGIN = os.getenv("ENABLE_BK_MONITOR_BASE_PLUGIN", "false").lower() == "true"


def _write_plugin_to_dir(plugin_configs: dict[Path, bytes], plugin_id: str) -> Path:
    """将内存中的插件文件物化到临时目录，生成 ``parse_metric_plugin_package`` 可直接解析的目录结构。

    上传阶段通过 ``parse_package_without_decompress`` 将导入包解压到内存
    （``dict[Path, bytes]``），其中插件文件的路径格式为
    ``<plugin_id>/external_plugins_*/...``。

    bk-monitor-base 的 ``parse_metric_plugin_package`` 要求根目录直接是
    ``external_plugins_*/``，因此写入磁盘时会去掉顶层的 ``<plugin_id>/`` 前缀。

    Note:
        由于 bk-monitor-base 的解析 API 基于文件系统操作（``Path.iterdir()``、
        ``open()``），不接受内存字典，所以这里必须先将 bytes 写到磁盘。

    Args:
        plugin_configs: 上传包中的插件文件映射，键为相对路径，值为文件内容。
        plugin_id: 要提取的目标插件 ID，用于从混合的 plugin_configs 中过滤文件。

    Returns:
        写入完成的临时目录路径。调用方负责在使用完毕后清理该目录。
    """
    tmp_dir = Path(tempfile.mkdtemp())
    for file_path, content in plugin_configs.items():
        p = Path(file_path)
        if len(p.parts) < 2 or p.parts[0] != plugin_id:
            continue
        dest = tmp_dir / Path(*p.parts[1:])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
    return tmp_dir


def _create_plugin_params_to_config(params: Any, meta_dict: dict[str, Any]) -> dict[str, Any]:
    """将 bk-monitor-base 的 ``CreatePluginParams`` 转换为 ``ImportParse`` 存储的 plugin_config 字典。

    解析阶段通过 ``parse_metric_plugin_package`` 得到 ``CreatePluginParams``（新格式），
    但 ``ImportParse.config`` 及下游 ``import_plugin`` 仍然使用旧格式字典（包含
    ``plugin_id``、``config_json``、``collector_json``、``metric_json`` 等字段）。

    其中 ``metric_json`` 通过 ``convert_metric_json_to_legacy`` 做 ``rules`` →
    ``rule_list`` 的转换并补齐 ``dimensions``、``is_diff_metric``、``is_manual``、
    ``tag_list`` 等旧字段，保证存储格式和旧模式一致，下游比较 MD5 或序列化器
    校验时不会因字段缺失而出错。

    Args:
        params: ``parse_metric_plugin_package`` 返回的 ``CreatePluginParams`` 实例。
        meta_dict: 从插件包 ``meta.yaml`` 中解析出的原始字典，用于提取
            ``tag`` 等 ``CreatePluginParams`` 不包含的字段。

    Returns:
        可直接存入 ``ImportParse.config`` 的扁平字典，格式与旧模式解析结果一致。
    """
    from monitor_web.plugin.compat import convert_metric_json_to_legacy, convert_plugin_type_to_legacy

    return {
        "plugin_id": params.id,
        "plugin_type": convert_plugin_type_to_legacy(params.type),
        "tag": meta_dict.get("tag", "") or "",
        "label": params.label,
        "config_json": [p.model_dump() if hasattr(p, "model_dump") else p for p in (params.params or [])],
        "collector_json": params.define or {},
        "is_support_remote": params.is_support_remote,
        "plugin_display_name": params.name,
        "description_md": params.description_md,
        "logo": params.logo or "",
        "metric_json": convert_metric_json_to_legacy(params.metrics or []),
        "enable_field_blacklist": params.enable_metric_discovery,
        "config_version": params.version.major,
        "info_version": params.version.minor,
        "version_log": params.version_log,
        "is_official": False,
        "is_safety": False,
        "signature": "",
    }


class BaseParse:
    def __init__(self, file_path, file_content={}, plugin_configs: dict[Path, bytes] = None):
        self.file_path = file_path
        self.file_content = file_content
        self.plugin_path = None
        self.plugin_configs = plugin_configs

    def read_file(self):
        with open(self.file_path) as fs:
            self.file_content = json.loads(fs.read())

    @abc.abstractmethod
    def check_msg(self):
        pass

    def parse_msg(self):
        self.read_file()
        return self.check_msg()


class CollectConfigParse(BaseParse):
    check_field = ["id", "name", "label", "collect_type", "params", "plugin_id", "target_object_type"]

    def only_check_fields(self):
        miss_filed = []
        for filed in self.check_field:
            if not self.file_content.get(filed):
                miss_filed.append(filed)

        if miss_filed:
            return {
                "file_status": ImportDetailStatus.FAILED,
                "name": self.file_content.get("name"),
                "collect_config": self.file_content,
                "error_msg": "miss filed {}".format(",".join(miss_filed)),
            }
        else:
            return {
                "file_status": ImportDetailStatus.SUCCESS,
                "collect_config": self.file_content,
            }

    def check_msg(self):
        if self.file_content.get("name") is None:
            return None

        fields_check_result = self.only_check_fields()
        if (
            self.file_content.get("collect_type", "")
            in [CollectConfigMeta.CollectType.LOG, CollectConfigMeta.CollectType.PROCESS]
            or fields_check_result["file_status"] == ImportDetailStatus.FAILED
        ):
            return fields_check_result

        plugin_id = self.file_content.get("plugin_id")
        if not self.get_plugin_path(plugin_id):
            return {
                "file_status": ImportDetailStatus.FAILED,
                "name": self.file_content.get("name"),
                "collect_config": self.file_content,
                "error_msg": _("缺少依赖的插件"),
            }

        if _USE_BASE_PLUGIN:
            return self._check_msg_new(plugin_id)
        return self._check_msg_old(plugin_id)

    def _check_msg_old(self, plugin_id: str):
        """旧模式：通过 ``PluginManagerFactory.get_tmp_version`` 解析插件并构建 plugin_config。

        Args:
            plugin_id: 需要解析的插件 ID。

        Returns:
            包含 ``file_status``、``collect_config``、``plugin_config`` 等键的字典；
            解析失败时 ``file_status`` 为 ``FAILED`` 并携带 ``error_msg``。
        """
        parse_plugin_config = self.parse_plugin_msg(plugin_id)
        if "config" in parse_plugin_config:
            parse_plugin_config["collect_config"] = parse_plugin_config["config"]
        if parse_plugin_config.get("tmp_version"):
            tmp_version = parse_plugin_config["tmp_version"]
            plugin_config = {}
            plugin_config.update(tmp_version.config.config2dict())
            plugin_config.update(tmp_version.info.info2dict())
            plugin_config.update(
                {
                    "plugin_id": tmp_version.plugin_id,
                    "plugin_type": tmp_version.plugin.plugin_type,
                    "tag": tmp_version.plugin.tag,
                    "label": tmp_version.plugin.label,
                    "signature": Signature(tmp_version.signature).dumps2yaml(),
                    "config_version": tmp_version.config_version,
                    "info_version": tmp_version.info_version,
                    "version_log": tmp_version.version_log,
                    "is_official": tmp_version.is_official,
                    "is_safety": tmp_version.is_safety,
                }
            )
            return {
                "file_status": ImportDetailStatus.SUCCESS,
                "collect_config": self.file_content,
                "plugin_config": plugin_config,
            }
        else:
            return parse_plugin_config

    def _check_msg_new(self, plugin_id: str):
        """新模式：通过 ``parse_metric_plugin_package`` 解析插件并构建 plugin_config。

        与 ``_check_msg_old`` 返回相同的字典结构，区别在于内部调用
        ``_parse_plugin_msg_new`` 使用 bk-monitor-base 的领域 API 完成解析。

        Args:
            plugin_id: 需要解析的插件 ID。

        Returns:
            包含 ``file_status``、``collect_config``、``plugin_config`` 等键的字典；
            解析失败时 ``file_status`` 为 ``FAILED`` 并携带 ``error_msg``。
        """
        parse_result = self._parse_plugin_msg_new(plugin_id)
        if "config" in parse_result:
            parse_result["collect_config"] = parse_result["config"]
        if "plugin_config" in parse_result:
            return {
                "file_status": ImportDetailStatus.SUCCESS,
                "collect_config": self.file_content,
                "plugin_config": parse_result["plugin_config"],
            }
        return parse_result

    def get_meta_path(self, plugin_id):
        """获取 meta.yaml 的路径"""
        meta_path = ""
        for file_path in self.plugin_configs.keys():
            if (
                str(file_path).split("/")[0] == plugin_id
                and file_path.parent.name == "info"
                and file_path.name == "meta.yaml"
            ):
                meta_path = file_path
                break
        return meta_path

    def parse_plugin_msg(self, plugin_id):
        meta_path = self.get_meta_path(plugin_id)

        if not meta_path:
            return {
                "file_status": ImportDetailStatus.FAILED,
                "name": self.file_content.get("name"),
                "config": self.file_content,
                "error_msg": _("关联插件信息不完整"),
            }
        try:
            meta_content = self.plugin_configs[meta_path]
            meta_dict = yaml.safe_load(meta_content)
            plugin_type_display = meta_dict.get("plugin_type")
            for name, display_name in CollectorPluginMeta.PLUGIN_TYPE_CHOICES:
                if display_name == plugin_type_display:
                    plugin_type = name
                    break
            else:
                raise PluginParseError({"msg": _("无法解析插件类型")})

            import_manager = PluginManagerFactory.get_manager(
                bk_tenant_id=get_request_tenant_id(),
                plugin=self.file_content.get("plugin_id"),
                plugin_type=plugin_type,
            )
            import_manager.filename_list = self.get_filename_list(plugin_id)
            import_manager.plugin_configs = self.plugin_configs
            info_path = {
                file_path.name: self.plugin_configs[file_path]
                for file_path in import_manager.filename_list
                if file_path.parent.name == "info"
            }

            tmp_version = import_manager.get_tmp_version(info_path=info_path)
            return {"tmp_version": tmp_version}
        except Exception as e:
            return {
                "file_status": ImportDetailStatus.FAILED,
                "name": self.file_content.get("name"),
                "config": self.file_content,
                "error_msg": _("关联插件信息解析失败: {e}".format(e=e)),
            }

    def _parse_plugin_msg_new(self, plugin_id: str) -> dict[str, Any]:
        """新模式：将内存中的插件文件写入临时目录，调用 bk-monitor-base 解析后返回 plugin_config。

        流程：
        1. 通过 ``_write_plugin_to_dir`` 将 ``self.plugin_configs`` 中属于
           ``plugin_id`` 的文件物化到临时目录。
        2. 调用 ``parse_metric_plugin_package`` 传入目录路径完成解析，
           得到 ``CreatePluginParams``。
        3. 通过 ``_create_plugin_params_to_config`` 转换为旧格式 dict。

        Args:
            plugin_id: 需要解析的插件 ID。

        Returns:
            解析成功时返回 ``{"plugin_config": dict}``；
            失败时返回 ``{"file_status": "failed", "name": ..., "config": ..., "error_msg": ...}``。
        """
        from bk_monitor_base.metric_plugin import parse_metric_plugin_package

        meta_path = self.get_meta_path(plugin_id)
        if not meta_path:
            return {
                "file_status": ImportDetailStatus.FAILED,
                "name": self.file_content.get("name"),
                "config": self.file_content,
                "error_msg": _("关联插件信息不完整"),
            }

        plugin_dir: Path | None = None
        try:
            meta_content = self.plugin_configs[meta_path]
            meta_dict = yaml.load(meta_content, Loader=yaml.FullLoader)

            plugin_dir = _write_plugin_to_dir(self.plugin_configs, plugin_id)
            bk_tenant_id: str = get_request_tenant_id() or ""
            operator: str = get_request_username() or "system"

            create_params = parse_metric_plugin_package(
                bk_tenant_id=bk_tenant_id,
                package_file=plugin_dir,
                operator=operator,
            )
            plugin_config = _create_plugin_params_to_config(create_params, meta_dict)
            return {"plugin_config": plugin_config}
        except Exception as e:
            return {
                "file_status": ImportDetailStatus.FAILED,
                "name": self.file_content.get("name"),
                "config": self.file_content,
                "error_msg": _("关联插件信息解析失败: {e}".format(e=e)),
            }
        finally:
            if plugin_dir is not None:
                shutil.rmtree(plugin_dir, ignore_errors=True)

    def get_filename_list(self, plugin_id: str) -> list[Path]:
        """获取插件的文件列表"""
        filename_list = []
        for file_path in self.plugin_configs.keys():
            if str(file_path).split("/")[0] == plugin_id:
                filename_list.append(file_path)

        return filename_list

    def get_plugin_path(self, plugin_id) -> bool:
        """
        遍历 self.plugin_configs 查找是否有包含 plugin_id 的路径
        """
        result = False
        for config_path in self.plugin_configs.keys():
            if str(config_path).split("/")[0] == plugin_id:
                result = True
                break
        return result


class StrategyConfigParse(BaseParse):
    def check_msg(self):
        if self.file_content.get("name") is None:
            return None

        return_data = {
            "file_status": ImportDetailStatus.SUCCESS,
            "config": self.file_content,
            "name": self.file_content.get("name"),
        }

        serializers = StrategySerializer(data=return_data["config"])
        try:
            serializers.is_valid(raise_exception=True)
        except ValidationError as e:

            def error_msg(value):
                for k, v in list(value.items()):
                    if isinstance(v, dict):
                        error_msg(v)
                    elif isinstance(v, list) and isinstance(v[0], ErrorDetail):
                        error_list.append(f"{k}{v[0][:-1]}")
                    else:
                        for v_msg in v:
                            error_msg(v_msg)

            error_list = []
            error_msg(e.detail)
            error_detail = "；".join(error_list)
            return_data.update(file_status=ImportDetailStatus.FAILED, error_msg=error_detail)

        action_list = return_data["config"]["actions"]
        for action_detail in action_list:
            for notice_detail in action_detail.get("user_group_list", []):
                if notice_detail.get("name") is None:
                    return_data.update(file_status=ImportDetailStatus.FAILED, error_msg=_("缺少通知组名称"))

        bk_collect_config_ids = []
        for query_config in return_data["config"]["items"][0]["query_configs"]:
            agg_condition = query_config.get("agg_condition", [])

            for condition_msg in agg_condition:
                if "bk_collect_config_id" not in list(condition_msg.values()):
                    continue

                if isinstance(condition_msg["value"], list):
                    bk_collect_config_ids.extend(
                        [int(value) for value in condition_msg["value"] if str(value).isdigit()]
                    )
                else:
                    bk_collect_config_id = condition_msg["value"].split("(")[0]
                    bk_collect_config_ids.append(int(bk_collect_config_id))

        return return_data, bk_collect_config_ids


class ViewConfigParse(BaseParse):
    def check_msg(self):
        if self.file_content.get("title") is None:
            return None

        return {
            "file_status": ImportDetailStatus.SUCCESS,
            "config": self.file_content,
            "name": self.file_content.get("title"),
        }
