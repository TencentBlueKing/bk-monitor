"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.db import models

from bkmonitor.utils.db import JsonField
from core.drf_resource import api
from constants.data_source import METRIC_TYPE_CHOICES, MetricType

from apm_web.models.application import Application
from common.log import logger


class MetricField(models.Model):
    """
    Metric 字段（指标字段 + 维度字段缓存）
    """

    bk_biz_id = models.IntegerField("业务id")
    app_name = models.CharField("应用名称", max_length=50)

    service_name = models.CharField("服务名称", max_length=255)

    # 监控项分组，数据来源（从上报数据中发现），默认值"default"
    scope_name = models.CharField("监控项分组名称", max_length=2048, default="default")

    type = models.CharField("字段类型", max_length=16, choices=METRIC_TYPE_CHOICES, default=MetricType.METRIC)
    name = models.CharField("字段名称", max_length=128)
    alias = models.CharField("字段别名", max_length=128, default="")

    is_disabled = models.BooleanField("是否禁用", default=False)

    config = models.JSONField("字段配置", default=dict)

    create_time = models.DateTimeField("创建时间", auto_now_add=True, null=True)
    update_time = models.DateTimeField("修改时间", auto_now=True, null=True)

    @classmethod
    def sync_from_metadata(cls, bk_biz_id, app_name, service_name):
        """
        从 metadata 中同步指标字段信息（待废弃，转为从 bkbase 中获取）
        """
        app = Application.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
        if not app:
            logger.info(f"bk_biz_id({bk_biz_id}) app({app_name}) not found")
            return

        if not app.time_series_group_id:
            logger.info(f"bk_biz_id({bk_biz_id}) app({app_name}) metric data source is disabled")
            return

        fields = {
            (o.scope_name, o.name): o
            for o in cls.objects.filter(
                bk_biz_id=bk_biz_id,
                app_name=app_name,
                # TODO service_name=service_name 暂时去掉该条件，待数据源支持
            )
        }
        results = api.metadata.get_time_series_group(time_series_group_id=app.time_series_group_id)
        for table in results:
            for metric_info in table["metric_info_list"]:
                """
                {'field_name': 'SayHello_request_count',
                  'metric_display_name': '',
                  'unit': '',
                  'type': 'float',
                  'tag_list': [{'field_name': 'target',
                    'description': '实体',
                    'unit': '',
                    'type': 'string'},
                   {'field_name': 'scope_name',
                    'description': '监控项',
                    'unit': '',
                    'type': 'string'},
                   {'field_name': 'namespace',
                    'description': '物理环境',
                    'unit': '',
                    'type': 'string'},
                   {'field_name': 'container_name',
                    'description': '容器名',
                    'unit': '',
                    'type': 'string'}],
                  'table_id': '2_bkapm_metric_tilapia.SayHello_request_count',
                  'description': '',
                  'is_disabled': False}
                """
                # TODO metadata的数据无法解析出 service_name, scope_name 等字段值，这里暂时留空
                # service_name = ""
                scope_name = "default"
                metric_name = metric_info["field_name"]

                old_metric = fields.get((scope_name, metric_name))
                if old_metric:
                    pass
                else:
                    fields[(scope_name, metric_name)] = cls.objects.create(
                        bk_biz_id=bk_biz_id,
                        app_name=app_name,
                        service_name=service_name,
                        scope_name=scope_name,
                        name=metric_name,
                        type=MetricType.METRIC,
                        config={
                            "dimensions": sorted([tag["field_name"] for tag in metric_info["tag_list"]]),
                            "unit": metric_info["unit"],
                            "label": [],
                        },
                        alias=metric_info["description"],
                        is_disabled=metric_info["is_disabled"],
                    )

                for dim in metric_info["tag_list"]:
                    old_dim = fields.get((scope_name, dim["field_name"]))
                    if old_dim:
                        pass
                    else:
                        fields[(scope_name, dim["field_name"])] = cls.objects.create(
                            bk_biz_id=bk_biz_id,
                            app_name=app_name,
                            service_name=service_name,
                            scope_name=scope_name,
                            name=dim["field_name"],
                            type=MetricType.DIMENSION,
                            alias=dim["description"],
                        )
                pass

    @classmethod
    def sync_from_bkdata(cls, bk_biz_id, app_name, service_name):
        app = Application.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
        if not app:
            logger.info(f"bk_biz_id({bk_biz_id}) app({app_name}) not found")
            return

        fields = {
            (o.scope_name, o.name): o
            for o in cls.objects.filter(
                bk_biz_id=bk_biz_id,
                app_name=app_name,
                # TODO service_name=service_name 暂时去掉该条件，待数据源支持
            )
        }
        from metadata.models import AccessVMRecord, BCSClusterInfo

        metric_result_table_id = app.metric_result_table_id
        try:
            vm_rt = AccessVMRecord.objects.get(result_table_id=metric_result_table_id).vm_result_table_id
        except AccessVMRecord.DoesNotExist:
            logger.info(f"bk_biz_id({bk_biz_id}) app({app_name}) sync metric field from bkdata failed")
            return

        # 获取指标
        data = (
            api.bkdata.query_metric_and_dimension(
                storage="vm",
                result_table_id=vm_rt,
                values=BCSClusterInfo.DEFAULT_SERVICE_MONITOR_DIMENSION_TERM,
            )
            or {}
        )

        if not data:
            return

        for md in data.get("metrics") or []:
            """
            {'name': 'trpc_ConnectionPoolIdleTimeout',
             'update_time': 1759192955510,
             'dimensions': [{'name': 'service_name',
               'update_time': 1759192955510,
               'values': []},
              {'name': 'env_name', 'update_time': 1759192955510, 'values': []},
              {'name': 'scope_name', 'update_time': 1759192955510, 'values': []},
              {'name': 'result_table_id', 'update_time': 1759192955510, 'values': []},
              {'name': 'namespace', 'update_time': 1759192955510, 'values': []},
              {'name': '_group', 'update_time': 1759192955510, 'values': []},
              {'name': 'container_name', 'update_time': 1759192955510, 'values': []},
              {'name': 'monitor_name', 'update_time': 1759192955510, 'values': []},
              {'name': 'instance', 'update_time': 1759192955510, 'values': []},
              {'name': 'sdk_name', 'update_time': 1759192955510, 'values': []},
              {'name': 'app_name', 'update_time': 1758810373740, 'values': []},
              {'name': 'version', 'update_time': 1759192955510, 'values': []},
              {'name': 'target', 'update_time': 1759192955510, 'values': []}]}
            """
            # TODO 这里需要解析出 service_name, scope_name 等字段值，这里暂时留空
            # service_name = ""
            scope_name = "default"

            metric_name = md["name"]
            dimensions = md["dimensions"]

            old_f = fields.get((scope_name, metric_name))
            if old_f:
                pass
            else:
                fields[(scope_name, metric_name)] = cls.objects.create(
                    bk_biz_id=bk_biz_id,
                    app_name=app_name,
                    service_name=service_name,
                    scope_name=scope_name,
                    name=metric_name,
                    type=MetricType.METRIC,
                )

            for dim in dimensions:
                old_dim = fields.get((scope_name, dim["name"]))
                if old_dim:
                    pass
                else:
                    fields[(scope_name, dim["name"])] = cls.objects.create(
                        bk_biz_id=bk_biz_id,
                        app_name=app_name,
                        service_name=service_name,
                        scope_name=scope_name,
                        name=dim["name"],
                        type=MetricType.DIMENSION,
                    )
            pass


class MetricCustomGroup(models.Model):
    """
    Metric 分组（指标自定义分组），仅针对未分组的指标，即 scope_name 为 default 的指标字段）
    """

    bk_biz_id = models.IntegerField("业务id")
    app_name = models.CharField("应用名称", max_length=50)

    service_name = models.CharField("服务名称", max_length=2048)

    name = models.CharField("分组名称", max_length=128)
    order = models.IntegerField("分组顺序", default=0)  # 该字段不需要，默认按字母顺序排序即可

    manual_list = JsonField("手动分组的指标列表", default=[])
    auto_rules = JsonField("自动分组的匹配规则列表", default=[])

    create_time = models.DateTimeField("创建时间", auto_now_add=True, null=True)
    update_time = models.DateTimeField("修改时间", auto_now=True, null=True)
