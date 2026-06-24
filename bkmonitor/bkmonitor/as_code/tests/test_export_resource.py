"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from types import SimpleNamespace

import yaml

from constants.action import NoticeChannel, NoticeWay
from monitor_web.as_code import resources as as_code_resources


class FakeDutyArrangeQuerySet:
    def __init__(self, items):
        self.items = items

    def only(self, *fields):
        return self

    def order_by(self, *fields):
        return self

    def __iter__(self):
        return iter(self.items)


def make_user_group():
    return SimpleNamespace(
        id=1,
        bk_biz_id=2,
        name="ops",
        desc="",
        channels=[NoticeChannel.WX_BOT],
        mention_list=[],
        mention_type=0,
        alert_notice=[],
        action_notice=[],
        need_duty=False,
        duty_rules=[],
        path="notice/ops.yaml",
    )


def patch_duty_arranges(monkeypatch, users=None):
    if users is None:
        users = [{"type": "user", "id": "admin"}]

    def filter_duty_arranges(**kwargs):
        assert kwargs == {"user_group_id__in": [1]}
        return FakeDutyArrangeQuerySet([SimpleNamespace(user_group_id=1, users=users)])

    monkeypatch.setattr(as_code_resources.DutyArrange.objects, "filter", filter_duty_arranges)


class FakeActionQuerySet:
    def values_list(self, *fields):
        assert fields == ("name", "id")
        return [("auto-heal", 3), ("callback", 5)]


def test_build_action_ids_by_config_ids_only_queries_referenced_actions(monkeypatch):
    captured_kwargs = {}

    def filter_actions(**kwargs):
        captured_kwargs.update(kwargs)
        return FakeActionQuerySet()

    monkeypatch.setattr(as_code_resources.ActionConfig.objects, "filter", filter_actions)

    result = as_code_resources.ExportConfigResource._build_action_ids_by_config_ids(2, [3, 5, 5])

    assert result == {"auto-heal": 3, "callback": 5}
    assert captured_kwargs == {"bk_biz_id__in": [2, 0], "id__in": {3, 5}}


def test_collect_referenced_action_config_ids():
    strategy_action_ids = as_code_resources.ExportConfigResource._get_strategy_action_config_ids(
        [
            {"actions": [{"config_id": 3}, {"config_id": 5}, {"config_id": 0}, {}]},
            {"actions": None},
        ]
    )
    assign_action_ids = as_code_resources.ExportConfigResource._get_assign_rule_action_config_ids(
        [
            {
                "rules": [
                    {
                        "actions": [
                            {"action_type": "notice", "action_id": 1},
                            {"action_type": "execute", "action_id": 7},
                            {"action_type": "execute", "action_id": 8},
                        ]
                    }
                ]
            }
        ]
    )

    assert strategy_action_ids == {3, 5}
    assert assign_action_ids == {7, 8}


def test_build_notice_group_export_configs(monkeypatch):
    user_group = make_user_group()
    patch_duty_arranges(monkeypatch)

    configs = as_code_resources.ExportConfigResource.build_notice_group_export_configs([user_group])

    assert configs == [
        {
            "id": user_group.id,
            "name": "ops",
            "bk_biz_id": 2,
            "desc": "",
            "path": "notice/ops.yaml",
            "channels": [NoticeChannel.WX_BOT],
            "mention_list": [{"type": "group", "id": "all"}],
            "action_notice": [],
            "alert_notice": [],
            "need_duty": False,
            "duty_arranges": [{"users": [{"type": "user", "id": "admin"}]}],
            "duty_rules": [],
        }
    ]


def test_export_notice_group_configs_keep_yaml_fields(monkeypatch):
    user_group = make_user_group()
    patch_duty_arranges(monkeypatch)

    configs = as_code_resources.ExportConfigResource.build_notice_group_export_configs([user_group])
    parser = as_code_resources.NoticeGroupConfigParser(bk_biz_id=2)
    exported_configs = list(
        as_code_resources.ExportConfigResource.transform_configs(
            parser=parser,
            configs=configs,
            with_id=False,
            lock_filename=False,
        )
    )

    assert len(exported_configs) == 1
    path, filename, content = exported_configs[0]
    assert path == "notice"
    assert filename == "ops.yaml"
    assert yaml.safe_load(content) == {
        "name": "ops",
        "channels": [NoticeChannel.WX_BOT],
        "version": "2.0",
        "action": {},
        "alert": {},
        "duty_rules": [],
        "mention_list": [{"member_type": "group", "id": "all"}],
        "users": ["admin"],
    }


def test_export_notice_group_configs_keep_empty_mentions_without_wx_bot(monkeypatch):
    user_group = make_user_group()
    user_group.channels = [NoticeChannel.USER]
    patch_duty_arranges(monkeypatch)

    configs = as_code_resources.ExportConfigResource.build_notice_group_export_configs([user_group])

    assert configs[0]["mention_list"] == []


def test_export_notice_group_configs_translate_legacy_wx_bot_notice_ways(monkeypatch):
    user_group = make_user_group()
    # 老结构只保存 type/chatid；旧详情序列化器会用 chatid 补齐 WX_BOT receivers。
    user_group.alert_notice = [
        {
            "time_range": "00:00:00--23:59:59",
            "notify_config": [
                {
                    "level": 1,
                    "type": [NoticeWay.WX_BOT],
                    "chatid": "robot-a,robot-b",
                }
            ],
        }
    ]
    patch_duty_arranges(monkeypatch)

    configs = as_code_resources.ExportConfigResource.build_notice_group_export_configs([user_group])
    notify_config = configs[0]["alert_notice"][0]["notify_config"][0]
    assert notify_config["notice_ways"] == [
        {"name": NoticeWay.WX_BOT, "receivers": ["robot-a", "robot-b"]},
    ]
    # 构造导出配置不能原地修改模型 JSON 字段，否则一次导出会影响后续逻辑看到的实例数据。
    assert "notice_ways" not in user_group.alert_notice[0]["notify_config"][0]

    parser = as_code_resources.NoticeGroupConfigParser(bk_biz_id=2)
    exported_configs = list(
        as_code_resources.ExportConfigResource.transform_configs(
            parser=parser,
            configs=configs,
            with_id=False,
            lock_filename=False,
        )
    )

    content = yaml.safe_load(exported_configs[0][2])
    assert content["alert"]["00:00--23:59"]["fatal"]["notice_ways"] == [
        {"name": NoticeWay.WX_BOT, "receivers": ["robot-a", "robot-b"]},
    ]


def test_export_notice_group_configs_keep_legacy_notice_without_type(monkeypatch):
    user_group = make_user_group()
    # 极老结构可能连 type 都没有；旧 DRF 字段会给 type/notice_ways 提供空列表默认值。
    user_group.alert_notice = [
        {
            "time_range": "00:00:00--23:59:59",
            "notify_config": [{"level": 1}],
        }
    ]
    patch_duty_arranges(monkeypatch)

    configs = as_code_resources.ExportConfigResource.build_notice_group_export_configs([user_group])

    assert configs[0]["alert_notice"][0]["notify_config"][0]["notice_ways"] == []

    parser = as_code_resources.NoticeGroupConfigParser(bk_biz_id=2)
    exported_configs = list(
        as_code_resources.ExportConfigResource.transform_configs(
            parser=parser,
            configs=configs,
            with_id=False,
            lock_filename=False,
        )
    )

    content = yaml.safe_load(exported_configs[0][2])
    assert content["alert"]["00:00--23:59"]["fatal"]["notice_ways"] == []


def test_export_notice_group_configs_deduplicate_members(monkeypatch):
    user_group = make_user_group()
    user_group.mention_type = 1
    # 旧路径经过 translate_user_display，会按 type--id 去重；导出侧只复刻去重，不做展示名翻译。
    user_group.mention_list = [
        {"type": "user", "id": "admin"},
        {"type": "user", "id": "admin"},
        {"type": "group", "id": "ops"},
    ]
    patch_duty_arranges(
        monkeypatch,
        users=[
            {"type": "user", "id": "admin"},
            {"type": "user", "id": "admin"},
            {"type": "group", "id": "ops"},
        ],
    )

    configs = as_code_resources.ExportConfigResource.build_notice_group_export_configs([user_group])

    assert configs[0]["mention_list"] == [
        {"type": "user", "id": "admin"},
        {"type": "group", "id": "ops"},
    ]
    assert configs[0]["duty_arranges"][0]["users"] == [
        {"type": "user", "id": "admin"},
        {"type": "group", "id": "ops"},
    ]

    parser = as_code_resources.NoticeGroupConfigParser(bk_biz_id=2)
    exported_configs = list(
        as_code_resources.ExportConfigResource.transform_configs(
            parser=parser,
            configs=configs,
            with_id=False,
            lock_filename=False,
        )
    )

    content = yaml.safe_load(exported_configs[0][2])
    assert content["mention_list"] == [
        {"member_type": "user", "id": "admin"},
        {"member_type": "group", "id": "ops"},
    ]
    assert content["users"] == ["admin", "group#ops"]


def test_export_notice_group_configs_ignore_duty_arranges_when_need_duty(monkeypatch):
    user_group = make_user_group()
    user_group.need_duty = True
    user_group.duty_rules = [100]
    patch_duty_arranges(monkeypatch, users=[{"type": "user", "id": "should-not-export"}])

    configs = as_code_resources.ExportConfigResource.build_notice_group_export_configs([user_group])
    parser = as_code_resources.NoticeGroupConfigParser(bk_biz_id=2, duty_rules={"primary": 100})
    exported_configs = list(
        as_code_resources.ExportConfigResource.transform_configs(
            parser=parser,
            configs=configs,
            with_id=False,
            lock_filename=False,
        )
    )

    content = yaml.safe_load(exported_configs[0][2])
    assert content["duty_rules"] == ["primary"]
    assert "users" not in content
