"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from packages.monitor_web.grafana.resources.unify_query import (
    GraphUnifyQueryResource,
    UnifyQueryRawResource,
)
from bkmonitor.utils.serializers import BkBizIdSerializer
from packages.monitor_web.as_code.resources import ImportConfigResource
from core.drf_resource import Resource
from bkmonitor.views import serializers

logger = logging.getLogger(__name__)


class KernelUnifyQueryRawResource(UnifyQueryRawResource):
    class RequestSerializer(UnifyQueryRawResource.RequestSerializer):
        with_metric = serializers.BooleanField(label="是否返回metric信息", default=False)


class KernelGraphUnifyQueryResource(GraphUnifyQueryResource):
    class RequestSerializer(GraphUnifyQueryResource.RequestSerializer):
        with_metric = serializers.BooleanField(label="是否返回metric信息", default=False)


class DashboardConfigSerializer(BkBizIdSerializer):
    """
    仪表盘配置序列化器基类
    """

    configs = serializers.DictField(required=True, label="文件内容")

    def validate_configs(self, configs: dict) -> dict:
        """
        校验并过滤configs，只保留仪表盘相关的配置（grafana/开头的路径）
        """
        if not configs:
            raise serializers.ValidationError("configs cannot be empty")

        filtered_configs = {}
        for path, content in configs.items():
            # 只保留 grafana/ 开头的路径
            if path.startswith("grafana/"):
                filtered_configs[path] = content

        if not filtered_configs:
            raise serializers.ValidationError("No valid dashboard config found, path must start with 'grafana/'")

        return filtered_configs


class CreateDashboardResource(Resource):
    """
    创建仪表盘配置（不覆盖同名配置）
    """

    RequestSerializer = DashboardConfigSerializer

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        logger.info("CreateDashboardResource: try to create dashboard, bk_biz_id: %s", bk_biz_id)

        return ImportConfigResource()(
            bk_biz_id=bk_biz_id,
            configs=validated_request_data["configs"],
            app="bkmonitor-mcp-app",
            overwrite=False,
            incremental=True,  # 只进行增量导入
        )


class UpdateDashboardResource(Resource):
    """
    更新仪表盘配置（覆盖同名配置）
    """

    RequestSerializer = DashboardConfigSerializer

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        logger.info("UpdateDashboardResource: try to update dashboard, bk_biz_id: %s", bk_biz_id)

        return ImportConfigResource()(
            bk_biz_id=bk_biz_id,
            configs=validated_request_data["configs"],
            app="bkmonitor-mcp-app",
            overwrite=True,
            incremental=True,  # 只进行增量导入
        )
