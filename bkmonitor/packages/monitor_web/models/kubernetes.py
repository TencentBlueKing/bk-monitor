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
from django.db import models


class BCSProjectModel(models.Model):
    id = models.IntegerField(primary_key=True)
    project_id = models.CharField(max_length=64, unique=True, db_index=True)
    cc_app_id = models.IntegerField(db_index=True)
    name = models.CharField(max_length=32)
    english_name = models.CharField(max_length=32)
    description = models.TextField()


class BCSClusterModel(models.Model):
    bk_biz_id = models.IntegerField("业务ID")
    project_id = models.CharField("项目ID")
    id = models.IntegerField(primary_key=True)
    cluster_id = models.CharField(max_length=128)
    cluster_number = models.IntegerField()
    name = models.CharField(max_length=128)
    status = models.CharField(max_length=128)
    disabled = models.BooleanField()
    environment = models.CharField()
    area_id = models.IntegerField()
    area_name = models.CharField()
    create_at = models.CharField()
    update_at = models.CharField()
    metrics = models.JSONField(default=dict)


class BCSAreaModel(models.Model):
    """
    bcs区域信息
    """

    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=64)
    chinese_name = models.CharField(max_length=64)
    description = models.TextField()


#
# class BCSResourceModel(models.Model):
#     """
#     bcs集群资源信息
#     """
#     bk_biz_id = models.IntegerField("业务ID")
#     project_id = models.CharField("项目ID", max_length=64)
#     cluster_id = models.CharField("集群ID", max_length=32)
#     resource = models.CharField("资源类型", max_length=64)
#     config = JSONField("资源配置")

# class BCSClusterConnectionModel(models.Model):
#     """
#     bcs集群连接信息
#     """
#     id = models.IntegerField(primary_key=True)
#     bk_biz_id = models.IntegerField("业务ID")
#     project_id = models.CharField("项目ID")
#     cluster_id = models.CharField("集群ID", db_index=True)
#     bcs_api_cluster_id = models.CharField("BCS集群ID")
#     domain_name = models.TextField()
#     port = models.IntegerField()
#     server_address_path = models.TextField()
#     api_key_prefix = models.TextField()
#     api_key_type = models.TextField()
#     api_key_content = models.TextField()
#     cert_content = models.TextField()
#
#     class Meta:
#         index_together = (("bk_biz_id", "cluster_id"),)
#         unique_together = ("bk_biz_id", "project_id", "cluster_id")
