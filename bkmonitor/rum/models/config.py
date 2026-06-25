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

from common.log import logger


class RumAppConfig(models.Model):
    """
    RUM 应用总配置表
    config_type 使用复合键格式 "大类:小类" 表达不同配置维度，例如：
      - "apdex:lcp"          → LCP 的 Apdex 阈值 (ms)
      - "qps:default"        → 全局 QPS 限制
    config_value 固定为 int，所有配置最终拆解为 type:subtype → int 映射。
    """

    APPLICATION_LEVEL = "application_level"  # scope_type 当前只支持 APPLICATION_LEVEL，scope_key 即 app_name

    id = models.BigAutoField(primary_key=True)
    bk_biz_id = models.IntegerField("业务id")
    app_name = models.CharField("应用名称", max_length=128)
    config_type = models.CharField(
        "配置类型",
        max_length=64,
        help_text="复合键格式 '大类:小类'，如 apdex:lcp / qps:default / sampler:percentage",
    )
    config_value = models.IntegerField("配置值")
    scope_type = models.CharField("配置作用类型", max_length=255, default=APPLICATION_LEVEL)
    scope_key = models.CharField("配置作用点", max_length=255, default="", help_text="APPLICATION_LEVEL 时为 app_name")

    class Meta:
        index_together = [["bk_biz_id", "app_name"]]

    @classmethod
    def refresh_config(
        cls,
        bk_biz_id,
        app_name,
        scope_type,
        scope_key,
        refresh_configs,
        need_delete_config=True,
        refresh_categories=None,
    ):
        """
        refresh_configs 格式: [{"config_type": "apdex:lcp", "config_value": 2500}, ...]
        delete_categories 用于限制删除范围，仅清理本次刷新涉及的大类配置。
        """
        create_objs = []
        exist_ids = []
        delete_categories = set(refresh_categories or [])
        if need_delete_config:
            exist_config_qs = cls.objects.filter(
                bk_biz_id=bk_biz_id,
                app_name=app_name,
                scope_type=scope_type,
                scope_key=scope_key,
            ).values("id", "config_type")
            if delete_categories:
                exist_ids = [
                    config["id"]
                    for config in exist_config_qs
                    if config["config_type"].split(":", 1)[0] in delete_categories
                ]
            else:
                exist_ids = [config["id"] for config in exist_config_qs]

        for config in refresh_configs:
            unique_params = {
                "bk_biz_id": bk_biz_id,
                "app_name": app_name,
                "config_type": config["config_type"],
                "scope_type": scope_type,
                "scope_key": scope_key,
            }

            qs = cls.objects.filter(**unique_params)
            qs_ids = list(qs.values_list("id", flat=True))
            exist_ids = [i for i in exist_ids if i not in qs_ids]

            if qs.exists():
                obj = qs.first()
                obj.config_value = config["config_value"]
                obj.save()
                # 清理重复记录
                repeat_ids = [i for i in qs_ids if i != obj.id]
                if repeat_ids:
                    cls.objects.filter(id__in=repeat_ids).delete()
                    logger.info(f"[RumAppConfig] delete repeat ids in {unique_params}")
                continue

            create_objs.append(cls(**unique_params, config_value=config["config_value"]))

        cls.objects.bulk_create(create_objs)
        if exist_ids:
            cls.objects.filter(id__in=exist_ids).delete()
        logger.info(f"[RumAppConfig] {bk_biz_id} {app_name} create {len(create_objs)} delete: {len(exist_ids)}")

    @classmethod
    def delete_config(cls, bk_biz_id, app_name, delete_configs):
        delete_ids = []
        for config in delete_configs:
            params = {
                "bk_biz_id": bk_biz_id,
                "app_name": app_name,
                "config_type": config["config_type"],
                "scope_type": config.get("scope_type", cls.APPLICATION_LEVEL),
                "scope_key": config.get("scope_key", app_name),
            }
            delete_ids.extend(list(cls.objects.filter(**params).values_list("id", flat=True)))
        if delete_ids:
            cls.objects.filter(id__in=delete_ids).delete()

    @classmethod
    def configs(cls, bk_biz_id, app_name, scope_type):
        """获取应用的指定配置"""
        return cls.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name, scope_type=scope_type)

    @classmethod
    def application_configs(cls, bk_biz_id, app_name):
        return cls.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name, scope_type=cls.APPLICATION_LEVEL)

    @classmethod
    def get_configs_by_category(cls, bk_biz_id, app_name, category):
        """
        按大类查询一组配置，如传入 "apdex" 会匹配 apdex:lcp / apdex:fcp / apdex:default 等。
        返回 {config_type: config_value} 字典。
        """
        qs = cls.objects.filter(
            bk_biz_id=bk_biz_id,
            app_name=app_name,
            config_type__startswith=f"{category}:",
        )
        return {item.config_type: item.config_value for item in qs}

    def to_json(self):
        return {
            "config_type": self.config_type,
            "config_value": self.config_value,
            "scope_type": self.scope_type,
            "scope_key": self.scope_key,
        }
