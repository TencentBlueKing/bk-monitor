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

from rest_framework import serializers

from bkmonitor.utils.request import get_request_tenant_id, get_request_username
from core.drf_resource import Resource, api
from core.drf_resource.exceptions import CustomException
from metadata.models import BCSClusterInfo

logger = logging.getLogger(__name__)


class GetBcsGrayClusterListResources(Resource):
    """
    获取BCS集群灰度ID名单
    """

    def perform_request(self, params):
        return {
            "enable_bsc_gray_cluster": False,
            "bcs_gray_cluster_id_list": [],
        }


class RegisterClusterResource(Resource):
    """
    集群接入
    """

    class RequestSerializer(serializers.Serializer):
        bcs_cluster_id = serializers.CharField(required=True, label="集群ID")
        username = serializers.CharField(required=False, label="用户名", allow_null=True, default="")

        def validate_username(self, username):
            if not username:
                username = get_request_username("admin")
            return username

    def perform_request(self, validated_request_data):
        bk_tenant_id = get_request_tenant_id()
        cluster_id = validated_request_data["bcs_cluster_id"]

        # 实时获取集群列表
        bcs_clusters = api.kubernetes.fetch_k8s_cluster_list.request.refresh(bk_tenant_id=bk_tenant_id)
        target_cluster = None
        for cluster in bcs_clusters:
            if cluster_id == cluster["cluster_id"]:
                target_cluster = cluster
                break
        # 判断集群是否存在
        if target_cluster is None:
            raise CustomException(f"[cluster]{cluster_id} not in bcs")

        # register
        try:
            bk_biz_id = target_cluster["bk_biz_id"]
            project_id = target_cluster["project_id"]
            cluster = BCSClusterInfo.register_cluster(
                bk_biz_id=bk_biz_id,
                cluster_id=cluster_id,
                project_id=project_id,
                creator=validated_request_data["username"],
                bk_tenant_id=bk_tenant_id,
            )
            cluster.init_resource()
            return f"[cluster]{cluster_id} success!"
        except ValueError:
            # 集群已存在
            if BCSClusterInfo.objects.filter(cluster_id=cluster_id).exists():
                return f"[cluster]{cluster_id} already registered. do nothing"
        except Exception as e:
            logger.exception(f"[cluster]{cluster_id} register error: {e}")
            # 失败回退灰度集群列表
            raise e
