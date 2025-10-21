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
from pathlib import Path

import yaml
from django.utils.translation import gettext as _
from rest_framework.exceptions import ErrorDetail, ValidationError

from bkmonitor.strategy.new_strategy import Strategy
from bkmonitor.utils.request import get_request_tenant_id
from core.errors.plugin import PluginParseError
from monitor_web.export_import.constant import ImportDetailStatus
from monitor_web.models import CollectConfigMeta, CollectorPluginMeta, Signature
from monitor_web.plugin.manager import PluginManagerFactory
from monitor_web.models.plugin import PluginVersionHistory


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

    def parse_result(self, error_msg=None):
        """统一解析结果"""
        result = {
            "file_status": ImportDetailStatus.SUCCESS if not error_msg else ImportDetailStatus.FAILED,
            "name": self.file_content.get("name"),
            "collect_config": self.file_content,
            "error_msg": error_msg or "",
        }

        return result

    def only_check_fields(self):
        miss_filed = []
        for filed in self.check_field:
            if not self.file_content.get(filed):
                miss_filed.append(filed)

        if miss_filed:
            return self.parse_result(error_msg=_("miss filed {}".format(",".join(miss_filed))))

        return self.parse_result()

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
            return self.parse_result(error_msg=_(f"缺少依赖的插件, plugin_id: {plugin_id}"))

        parse_plugin_config = self.parse_plugin_msg(plugin_id)
        if parse_plugin_config.get("tmp_version"):
            tmp_version: PluginVersionHistory = parse_plugin_config["tmp_version"]
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

            result = self.parse_result()
            result["plugin_config"] = plugin_config

            return result
        else:
            return self.parse_result(error_msg=_(parse_plugin_config["error_msg"]))

    def get_meta_path(self, plugin_id):
        """获取 meta.yaml 的路径"""
        meta_path = ""
        for file_path in self.plugin_configs.keys():
            if (
                Path(file_path).parts[0] == plugin_id
                and file_path.parent.name == "info"
                and file_path.name == "meta.yaml"
            ):
                meta_path = file_path
                break
        return meta_path

    def parse_plugin_msg(self, plugin_id) -> dict[str, PluginVersionHistory | str]:
        meta_path = self.get_meta_path(plugin_id)

        if not meta_path:
            return {"error_msg": "关联插件信息不完整,缺少'meta.yaml'文件路径"}

        try:
            meta_content = self.plugin_configs[meta_path]
            meta_dict = yaml.load(meta_content, Loader=yaml.FullLoader)
            plugin_type_display = meta_dict.get("plugin_type")
            for name, display_name in CollectorPluginMeta.PLUGIN_TYPE_CHOICES:
                if display_name == plugin_type_display:
                    plugin_type = name
                    break
            else:
                raise PluginParseError({"msg": _(f"无法解析插件类型, plugin_type: {plugin_type_display}")})

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

            tmp_version: PluginVersionHistory = import_manager.get_tmp_version(info_path=info_path)
            return {"tmp_version": tmp_version}
        except Exception as e:
            return {"error_msg": _(f"关联插件信息解析失败, error: {e}")}

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
            "config": Strategy.convert_v1_to_v2(self.file_content),
            "name": self.file_content.get("name"),
        }

        serializers = Strategy.Serializer(data=return_data["config"])
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
