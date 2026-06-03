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

from constants.action import NoticeChannel
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
