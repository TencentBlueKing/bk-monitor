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


class ImportDashboardResource(Resource):
    """
    增量导入仪表盘配置
    """
    class RequestSerializer(BkBizIdSerializer):
        configs = serializers.DictField(required=True, label="文件内容")
        overwrite = serializers.BooleanField(default=False, label="是否覆盖同名配置")

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        logger.info("ImportDashBoardResource: try to import dashboard, bk_biz_id: %s", bk_biz_id)

        return ImportConfigResource()(
            bk_biz_id=validated_request_data["bk_biz_id"],
            configs=validated_request_data["configs"],
            app="bkmonitor-mcp-app",
            overwrite=validated_request_data["overwrite"],
            incremental=True    # 只进行增量导入
        )
