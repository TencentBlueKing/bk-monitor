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
from django.core.management import BaseCommand

from metadata.task.auto_deploy_proxy import AutoDeployProxy


class Command(BaseCommand):
    """通过节点管理，部署 proxy 和 collector 插件

    1. 用户在监控平台`全局配置`中设置需要`自定义上报默认服务器`的 IP
    2. 如果有对应的域名，可以填写上域名信息，此后页面将屏蔽具体IP的展示
    3. 执行命令，部署 proxy 和 collector 插件
    """

    def handle(self, *args, **options):
        AutoDeployProxy.refresh("bk-collector")

        print("bkmonitorproxy and bk-collector deployed successfully!")
