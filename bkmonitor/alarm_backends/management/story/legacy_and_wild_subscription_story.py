# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import json
import sys

import requests

from alarm_backends.management.story.base import (
    BaseStory,
    CheckStep,
    Problem,
    StepController,
    register_step,
    register_story,
)

try:
    from conf.api.production.gunicorn_config import bind
except Exception as e:
    print(f"get bind address failed: {e}")
    bind = ""


class WildEntry(StepController):
    def _check(self):
        return "-wild" in sys.argv


wild_controller = WildEntry()


@register_story()
class NodemanStory(BaseStory):
    name = "Nodeman legacy and wild subscription Check"


@register_step(NodemanStory)
class LegacyAndWildSubscriptionNumber(CheckStep):
    name = "check legacy and wild subscription number"
    controller = wild_controller

    def check(self):
        if not bind:
            self.story.info("Error, Can't get bind url.")
        headers = {"bk_app_code": "bk_monitorv3", "bk_username": "admin"}

        problems = []

        legacy_subscriptions = json.loads(
            requests.get(f"http://{bind}/api/v4/collect/list_legacy_subscription/", headers=headers).text
        ).get("data", [])

        total_legacy_subscription_ids = legacy_subscriptions["total_legacy_subscription_ids"]
        wild_subscription_ids = legacy_subscriptions["wild_subscription_ids"]

        # 升级残留订阅
        if len(total_legacy_subscription_ids) > 0:
            warn_text = (
                f"total legacy subscription_ids number: [{len(total_legacy_subscription_ids)}] "
                f"id: {total_legacy_subscription_ids}"
            )
            if len(total_legacy_subscription_ids) > 5:
                problems.append(LegacySubscriptionsProblem(warn_text, self.story))
            else:
                self.story.warning(warn_text)
        else:
            self.story.info("total legacy subscription_ids number: 0")

        # 野订阅
        if len(wild_subscription_ids) > 0:
            warn_text = (
                f"total wild subscription_ids number: [{len(wild_subscription_ids)}]" f"id: {wild_subscription_ids}"
            )

            if len(wild_subscription_ids) > 5:
                problems.append(WildSubscriptionsProblem(warn_text, self.story))
            else:
                self.story.warning(warn_text)
        else:
            self.story.info("total wild subscription_ids number: 0")

        return problems


class LegacySubscriptionsProblem(Problem):
    def position(self):
        self.story.warning("建议：升级残留订阅过多(>5), 请清理相关的订阅ID")


class WildSubscriptionsProblem(Problem):
    def position(self):
        self.story.warning("建议：野订阅数量过多(>5), 请清理相关的订阅ID")
