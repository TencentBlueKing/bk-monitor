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
import logging
from typing import Any, Dict, List

from django.core.management import BaseCommand
from django.utils.translation import ugettext_lazy as _

from apm_web.handlers.metric_group import MetricHelper
from apm_web.handlers.strategy_group import (
    BaseStrategyGroup,
    GroupType,
    RPCApplyType,
    StrategyGroupRegistry,
)

logging.basicConfig(format="%(levelname)s [%(asctime)s] %(name)s | %(message)s", level=logging.INFO)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('-b', "--bk_biz_id", type=int, help=_("业务ID"))
        parser.add_argument('-a', "--app_name", type=str, help=_("应用名"))
        parser.add_argument(
            "-t",
            "--apply-types",
            nargs="+",
            type=str,
            default=[RPCApplyType.CALLEE.value, RPCApplyType.CALLER.value],
            choices=RPCApplyType.options(),
            help=_("应用告警策略类型列表"),
        )
        parser.add_argument("-t", "--apply-servers", nargs="+", type=str, default=[], help=_("服务列表"))
        parser.add_argument("-g", "--notice-group-ids", nargs="+", type=int, help=_("告警组 ID 列表"))
        parser.add_argument("--config", type=str, default="{}", help=_("配置"))

    def handle(self, *args, **options):
        bk_biz_id: int = options["bk_biz_id"]
        app_name: str = options["app_name"]
        apply_types: List[str] = list(options.get("apply_types") or [])
        apply_servers: List[str] = list(options.get("apply_servers") or [])
        notice_group_ids: List[int] = options["notice_group_ids"]
        options_config: Dict[str, Any] = json.loads(options.get("config") or "{}")

        logger.info(
            "[apply_rpc_strategies] received params: \n"
            "bk_biz_id -> %s, \n"
            "app_name -> %s, \n"
            "apply_types -> %s, \n"
            "apply_servers -> %s, \n"
            "notice_group_ids -> %s \n"
            "config -> %s",
            bk_biz_id,
            app_name,
            apply_types,
            apply_servers,
            notice_group_ids,
            json.dumps(options_config, indent=2),
        )

        metric_helper = MetricHelper(bk_biz_id, app_name)
        group: BaseStrategyGroup = StrategyGroupRegistry.get(
            GroupType.RPC.value,
            bk_biz_id,
            app_name,
            metric_helper=metric_helper,
            notice_group_ids=notice_group_ids,
            apply_types=apply_types,
            apply_servers=apply_servers,
            options=options_config,
        )
        group.apply()