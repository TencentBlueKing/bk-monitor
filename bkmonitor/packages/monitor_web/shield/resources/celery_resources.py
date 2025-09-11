# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


from core.drf_resource.base import Resource
from bkmonitor.models import Shield
from bkmonitor.utils.common_utils import logger
from bkmonitor.utils.local import local
from bkmonitor.utils.time_tools import now
from monitor_web.shield.utils import ShieldDisplayManager
from utils import business


class UpdateFailureShieldContentResource(Resource):
    """
    更新失效屏蔽的内容
    """

    def __init__(self):
        super(UpdateFailureShieldContentResource, self).__init__()

    def perform_request(self, data):
        logger.info("start celery period task: update failure shield content")
        # 查找失效且屏蔽内容为空的屏蔽配置
        shield_list = list(Shield.objects.filter(failure_time__lte=now(), content="").values())
        # 引入屏蔽展示工具类
        shield_display_manager_dict = {}
        for shield in shield_list:
            local.username = business.maintainer(str(shield["bk_biz_id"]))
            shield_display_manager = shield_display_manager_dict.setdefault(
                shield["bk_biz_id"], ShieldDisplayManager(shield["bk_biz_id"])
            )
            content = shield_display_manager.get_shield_content(shield)
            Shield.objects.filter(id=shield["id"]).update(content=content)
