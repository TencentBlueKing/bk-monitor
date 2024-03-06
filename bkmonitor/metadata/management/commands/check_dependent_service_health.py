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

from django.conf import settings
from django.core.management.base import BaseCommand

from core.drf_resource import api


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--check_bkcc", action="store", default="True", help="check bkcc service")
        parser.add_argument(
            "--check_bcs_project_manager", action="store", default="True", help="check bcs project manager service"
        )
        parser.add_argument(
            "--check_bcs_cluster_manager", action="store", default="True", help="check bcs cluster manager service"
        )

    def handle(self, *args, **options):
        check_bkcc, check_bcs_project_manager, check_bcs_cluster_manager = (
            options.get("check_bkcc"),
            options.get("check_bcs_project_manager"),
            options.get("check_bcs_cluster_manager"),
        )
        # 校验依赖服务
        self._check_bkcc_health(check_bkcc)
        self._check_bcs_project_manager_health(check_bcs_project_manager)
        self._check_bcs_cluster_manager_health(check_bcs_cluster_manager)

        self.stderr.write("check service end!")

    def _check_bkcc_health(self, check_bkcc: bool) -> None:
        """校验 bkcc 服务正常"""
        if check_bkcc not in ["true", "True"]:
            return

        self.stdout.write("check bkcc service start")
        try:
            # 通过查询接口判断
            api.cmdb.get_business()
        except Exception as e:
            msg = f"request bkcc biz api error, {e}"
            self.stderr.write(msg)

        self.stdout.write("check bkcc service end")

    def _check_bcs_project_manager_health(self, check_bcs_project_manager: bool) -> None:
        """校验 bcs project 服务正常"""
        if check_bcs_project_manager not in ["true", "True"]:
            return

        self.stdout.write("check bcs project manager service start")
        try:
            project_list = (
                api.bcs_cc.batch_get_projects()
                if settings.ENABLE_BCS_CC_PROJECT_API
                else api.bcs.get_projects(kind="k8s")
            )
        except Exception as e:
            msg = f"request bcs project manager api error, {e}"
            self.stderr.write(msg)
            return
        # 依赖环境项目肯定存在
        if len(project_list) == 0:
            self.stderr.write("project is null")

        self.stdout.write("check bcs project manager service end")

    def _check_bcs_cluster_manager_health(self, check_bcs_cluster_manager: bool) -> None:
        """校验 bcs cluster 服务正常"""
        if check_bcs_cluster_manager not in ["true", "True"]:
            return

        self.stdout.write("check bcs cluster manager service start")
        try:
            cluster_list = api.bcs_cluster_manager.get_project_clusters()
        except Exception as e:
            msg = f"request bcs cluster manager api error, {e}"
            self.stderr.write(msg)
            return
        # 依赖环境集群肯定存在
        if len(cluster_list) == 0:
            self.stderr.write("cluster is null")

        self.stdout.write("check bcs cluster manager service end")
