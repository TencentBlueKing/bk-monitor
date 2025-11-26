"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import os

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.translation import gettext as _

from bkmonitor.documents.tasks import rollover_indices
from bkmonitor.models import EventPluginInstance, EventPluginV2
from constants.action import GLOBAL_BIZ_ID
from fta_web.event_plugin.handler import PackageHandler
from fta_web.event_plugin.resources import (
    CreateEventPluginInstanceResource,
    UpdateEventPluginInstanceResource,
)


def register_builtin_plugins(sender, **kwargs):
    import json
    import os

    from django.conf import settings

    from bkmonitor.models.fta import ActionPlugin

    print("start to  register_builtin_plugin ")
    initial_file = os.path.join(settings.PROJECT_ROOT, "support-files/fta/action_config_incident_manager.json")
    # 注册故障分析SaaS插件服务，取决于是否开启和部署
    try:
        ActionPlugin.origin_objects.count()
    except Exception:
        # 首次部署，表未就绪
        return
    with open(initial_file, encoding="utf-8") as f:
        plugins = json.loads(f.read())
        for plugin in plugins:
            # 多租户情况下禁用itsmv3插件
            if plugin["plugin_key"] == "itsm" and settings.ENABLE_MULTI_TENANT_MODE:
                continue

            # 开启标准排障的情况下,才可注册标准排障插件
            if plugin["plugin_key"] == "bk_incident" and not settings.ENABLE_BK_INCIDENT_PLUGIN:
                continue
            instance, created = ActionPlugin.origin_objects.update_or_create(
                id=plugin.pop("id"), is_builtin=True, defaults=plugin
            )
            print("{} plugin: [{}]".format("register" if created else "update", instance.name))


def register_builtin_action_configs(sender, **kwargs):
    import json
    import os

    from django.conf import settings

    from bkmonitor.models.fta import ActionConfig

    print("start to register_builtin_action_configs")
    initial_file = os.path.join(settings.PROJECT_ROOT, "support-files/fta/action_config_initial.json")

    with open(initial_file, encoding="utf-8") as f:
        action_configs = json.loads(f.read())
        for action_config in action_configs:
            instance, created = ActionConfig.origin_objects.update_or_create(
                id=action_config.pop("id"), defaults=action_config
            )
            print("{} action_config: [{}]".format("register" if created else "update", instance.name))


def migrate_actions(sender, **kwargs):
    """
    迁移监控的告警以及webhook至自愈套餐配置
    """
    import json

    from bkmonitor.action.serializers import ActionConfigDetailSlz, UserGroupDetailSlz
    from bkmonitor.models import (
        Action,
        ActionConfig,
        ActionNoticeMapping,
        GlobalConfig,
        ItemModel,
        NoticeGroup,
        NoticeTemplate,
        StrategyActionConfigRelation,
        StrategyModel,
    )
    from constants.action import ActionSignal

    if GlobalConfig.objects.filter(key="MIGRATE_ACTIONS_OPERATE", value="1").exists():
        print("New action config is ready for FTA ^_^")
        return

    strategies = {item["id"]: item["name"] for item in StrategyModel.objects.all().values("name", "id")}

    def add_new_user_group(old_group: NoticeGroup):
        new_group = {
            "name": old_group.name,
            "desc": old_group.message,
            "bk_biz_id": old_group.bk_biz_id,
            "source": old_group.source,
            "duty_arranges": [
                {
                    "users": [
                        {"type": receiver.split("#")[0], "id": receiver.split("#")[-1]}
                        for receiver in old_group.notice_receiver
                    ]
                }
            ],
        }
        new_user_group_slz = UserGroupDetailSlz(data=new_group)
        new_user_group_slz.is_valid(raise_exception=True)
        new_user_group_slz.save()
        return new_user_group_slz.instance

    def add_notice_action(notice_way, old_action_config, wxwork_group=None):
        notice_actions = []
        try:
            notice_template = NoticeTemplate.objects.get(action_id=old_action_config.id)
        except NoticeTemplate.DoesNotExist:
            notice_template = None

        notice_ways = [{"level": level, "type": notice_type} for level, notice_type in notice_way.items()]
        wxwork_group = wxwork_group or {}
        for level_notice_way in notice_ways:
            if level_notice_way["level"] in wxwork_group:
                level_notice_way["type"].append("wxwork-bot")
                level_notice_way["chatid"] = wxwork_group[level_notice_way["level"]]

            level_notice_way["type"] = ",".join(level_notice_way["type"])

        alarm_interval = old_action_config.config["alarm_interval"]
        notice_config_tmpl = {
            "converge_config": {
                "timedelta": 5 * 60,
                "count": 1,
                "condition": [
                    {"dimension": "bk_biz_id", "value": ["self"]},
                    {"dimension": "strategy_id", "value": ["self"]},
                ],
                "converge_func": "collect",
            },
            "execute_config": {
                "template_detail": {
                    "notify_config": {
                        "notify_type": notice_ways,
                        "message_tmpl": "",
                    },
                    "notify_time_range": "{alarm_start_time}--{alarm_end_time}".format(**old_action_config.config),
                    "notify_interval": alarm_interval * 60,
                    "interval_notify_mode": "standard",
                },
                "timeout": 60,
                "failed_retry": {"is_enabled": False, "max_retry_times": 0, "retry_interval": 0},
            },
            "name": _("%s{signal_name}通知") % strategies.get(old_action_config.strategy_id, "自愈迁移"),
            "desc": _("迁移的通知套餐"),
            "is_enabled": True,
            "plugin_id": 1,
            "bk_biz_id": old_action_config.bk_biz_id,
        }
        anomaly_message_tmpl = "" if notice_template is None else notice_template.anomaly_template
        recovery_message_tmpl = "" if notice_template is None else notice_template.recovery_template

        notice_actions.append(add_notice_config(notice_config_tmpl, anomaly_message_tmpl))

        if old_action_config.config["send_recovery_alarm"]:
            # 创建恢复信号告警
            notice_actions.append(add_notice_config(notice_config_tmpl, recovery_message_tmpl, ActionSignal.RECOVERED))

        no_data_tmpl = ""
        for item in ItemModel.objects.filter(strategy_id=old_action.strategy_id):
            if not item.no_data_config.get("is_enabled"):
                continue
            # 开启了无数据告警，则创建无数据告警事件
            notice_actions.append(add_notice_config(notice_config_tmpl, no_data_tmpl, ActionSignal.NO_DATA))

        return notice_actions

    def add_notice_config(notice_config_tmpl, message_tmpl, action_signal=ActionSignal.ABNORMAL):
        notice_tmpl = json.loads(json.dumps(notice_config_tmpl))
        notice_tmpl["execute_config"]["template_detail"]["notify_config"]["message_tmpl"] = message_tmpl
        notice_tmpl["name"] = notice_tmpl["name"].format(signal_name=ActionSignal.ACTION_SIGNAL_DICT[action_signal])

        ac_slz = ActionConfigDetailSlz(data=notice_tmpl)
        ac_slz.is_valid(raise_exception=True)
        ac_slz.save()
        return action_signal, ac_slz.instance

    def add_webhook_action(url, old_action_config: Action) -> (str, ActionConfig):
        webhook_action_config = {
            "name": _("HTTP回调[%s]") % old_action_config.id,
            "plugin_id": 2,
            "bk_biz_id": old_action_config.bk_biz_id,
            "desc": "",
            "converge_config": {
                "timedelta": 300,
                "count": 1,
                "condition": [{"dimension": "bk_host_id", "value": ["self"]}],
                "converge_func": "skip_when_proceed",
            },
            "execute_config": {
                "template_detail": {
                    "method": "POST",
                    "url": url,
                    "headers": [],
                    "authorize": {"auth_type": "none", "auth_config": {}},
                    "body": {
                        "data_type": "raw",
                        "params": [],
                        "content": "",
                        "content_type": "json",
                    },
                    "query_params": [],
                },
                "notify_config": {
                    "notify_type": [
                        {"level": 1, "type": "mail"},
                        {"level": 2, "type": "mail"},
                        {"level": 3, "type": "mail"},
                    ],
                    "message_tmpl": "",
                },
                "failed_retry": {"is_enabled": True, "max_retry_times": 2, "retry_interval": 60},
                "timeout": 600,
            },
        }

        ac_slz = ActionConfigDetailSlz(data=webhook_action_config)
        ac_slz.is_valid()
        ac_slz.save()
        return ActionSignal.ABNORMAL, ac_slz.instance

    strategy_action_relations = []
    for old_notice_group in NoticeGroup.objects.all():
        new_user_group = add_new_user_group(old_notice_group)
        action_ids = ActionNoticeMapping.objects.filter(notice_group_id=old_notice_group.id).values_list(
            "action_id", flat=True
        )

        if not action_ids:
            continue
        old_actions = Action.objects.filter(id__in=action_ids)

        for old_action in old_actions:
            new_actions = []
            old_action.bk_biz_id = old_notice_group.bk_biz_id
            if old_notice_group.webhook_url:
                new_actions.append(add_webhook_action(old_notice_group.webhook_url, old_action))
            new_actions.extend(
                add_notice_action(old_notice_group.notice_way, old_action, old_notice_group.wxwork_group)
            )
            strategy_id = old_action.strategy_id
            for signal, new_action in new_actions:
                strategy_action_relations.append(
                    StrategyActionConfigRelation(
                        config_id=new_action.id, user_groups=[new_user_group.id], strategy_id=strategy_id, signal=signal
                    )
                )

    StrategyActionConfigRelation.objects.bulk_create(strategy_action_relations)
    GlobalConfig.objects.update_or_create(key="MIGRATE_ACTIONS_OPERATE", defaults={"value": 1})


def rollover_es_indices(sender, **kwargs):
    rollover_indices()


def register_global_event_plugin(sender, **kwargs):
    """
    注册内置的告警源插件
    :param sender:
    :param kwargs:
    :return:
    """
    builtin_params = [
        {
            "field": "begin_time",
            "name": _("开始时间"),
            "value": "{{begin_time}}",
            "is_required": True,
            "is_hidden": True,
            "default_value": "{{begin_time}}",
        },
        {
            "field": "end_time",
            "name": _("结束时间"),
            "value": "{{end_time}}",
            "is_required": True,
            "is_hidden": True,
            "default_value": "{{end_time}}",
        },
    ]
    register_event_plugin(builtin_params)


def register_event_plugin(config_params=None, all_alarm_types=None):
    from fta_web.event_plugin.resources import CreateEventPluginResource

    plugins = {}
    document_root = os.path.join(settings.PROJECT_ROOT, "support-files/fta/event_plugins")

    def is_exist_plugin(plugin_id: str, version: str) -> bool:
        """
        通过文件名对应插件ID与插件版本来判断当前的插件是否存在
        :param plugin_id: 插件ID
        :param version: 插件版本
        :return: True: 不存在 False: 存在
        """
        if EventPluginV2.objects.filter(plugin_id=plugin_id, version=version).exists():
            print(f"[event plugin initial]  plugin({file_path}) already existed")
            return True
        return False

    for plugin_file in os.listdir(document_root):
        try:
            file_path = os.path.join(document_root, plugin_file)
            if not os.path.isfile(file_path):
                continue
            # 判断是否存在，同时从文件名称拆分id与version
            pure_plugin_file_name = plugin_file.rsplit(".tar.gz")[0]
            if not pure_plugin_file_name:
                print(f"[event plugin initial] none plugin: {file_path}")
                continue
            plugin_version_info = pure_plugin_file_name.rsplit("__", 1)
            plugin_id = plugin_version_info[0]
            version = plugin_version_info[1] if len(plugin_version_info) == 2 else "1.0.0"  # 命名没有默认1.0.0

            if is_exist_plugin(plugin_id=plugin_id, version=version):
                continue
            print(f"[event plugin initial] package to import: {file_path}")
            with open(file_path, "rb") as tar_obj:
                file_data = SimpleUploadedFile("plugin.tar.gz", tar_obj.read())
                handler = PackageHandler.from_tar_file(file_data)
                plugin_info = handler.parse()
                if plugin_info["plugin_id"] == "rest_pull" and config_params:
                    plugin_info["config_params"] = config_params
                if all_alarm_types and all_alarm_types.get(plugin_info["plugin_id"]):
                    if "alert_config" in plugin_info:
                        plugin_info["alert_config"].extend(all_alarm_types[plugin_info["plugin_id"]])
                    else:
                        plugin_info["alert_config"] = all_alarm_types[plugin_info["plugin_id"]]
                plugin_info["bk_biz_id"] = 0
                plugin_info["version"] = plugin_info.get("version") or "1.0.0"
                if not (plugin_id == plugin_info["plugin_id"] and version == plugin_info["version"]):
                    print(
                        "[event plugin initial] match pluginId or version error, "
                        "plugin:{}, plugin_id：{} version：{}".format(
                            plugin_file, plugin_info["plugin_id"], plugin_info["version"]
                        )
                    )
                    continue
                try:
                    plugin = CreateEventPluginResource().perform_request(plugin_info)
                except BaseException as error:
                    print("[fta migration] create plugin({}) error: {}".format(plugin_info["plugin_id"], str(error)))
                    continue
                EventPluginV2.objects.filter(plugin_id=plugin["plugin_id"], version=plugin["version"]).update(
                    package_dir=handler.get_package_dir()
                )
            plugins[plugin["plugin_id"]] = plugin
            print(
                "[register] create plugin success, plugin_id({}), version({})".format(
                    plugin["plugin_id"], plugin["version"]
                )
            )
        except BaseException as error:
            print(f"[register] create plugin error, plugin_file({plugin_file}), error info{str(error)}")
    return plugins


def install_global_event_plugin(plugin):
    # 创建安装配置， 默认用全局内容

    print(
        "[fta migration] start to install global plugin plugin_id({}), version({})".format(
            plugin["plugin_id"], plugin["version"]
        )
    )
    inst_info = {
        "bk_biz_id": GLOBAL_BIZ_ID,
        "plugin_id": plugin["plugin_id"],
        "version": plugin["version"],
        "config_params": {param["field"]: param["default_value"] for param in plugin["config_params"]},
    }
    if EventPluginInstance.objects.filter(
        bk_biz_id=0, plugin_id=plugin["plugin_id"], version=plugin["version"]
    ).exists():
        inst_data = UpdateEventPluginInstanceResource().request(inst_info)
    else:
        inst_data = CreateEventPluginInstanceResource().request(inst_info)

    print(
        "[fta migration] install global plugin success, plugin_id({}), version({}), instance_data_id({})".format(
            plugin["plugin_id"], plugin["version"], inst_data["data_id"]
        )
    )
