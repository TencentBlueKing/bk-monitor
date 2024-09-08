"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2024 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from typing import Dict, List, Union

from monitor_web.models.collecting import DeploymentConfigVersion

from .base import BaseInstaller


class K8sInstaller(BaseInstaller):
    """
    k8s安装器
    """

    def install(self, install_config: Dict):
        pass

    def uninstall(self):
        pass

    def rollback(self, deployment_config_version: Union[int, DeploymentConfigVersion, None] = None):
        pass

    def start(self):
        pass

    def stop(self):
        pass

    def retry(self, instance_ids: List[str] = None):
        pass

    def revoke(self, instance_ids: List[int] = None):
        pass

    def status(self, *args, **kwargs):
        pass
